/**
 * M5b acceptance in the browser (contract 9): the dossier page is the whole workflow. organizer-fsi creates a draft, writes
 * the howto, drops a poster and publishes it (the feed carries the image); a second event goes out without a poster (banner,
 * feed `image: null`); an archived event becomes the template of a new draft with the copied howto; cancel, unpublish and
 * restore work from the action bar. Both themes through axe, at desktop width and at 360 px.
 */
import { type APIRequestContext, type Browser, type Page, expect, request, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { createDossier, runAction, setSummary, toSection, uploadPoster } from './support/dossier';
import { eventOf, login, waitForCleanPoster } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const title = (name: string): string => `E2E M5b ${name} ${STAMP}`;
const HOWTO = `Anleitung ${STAMP}: Beamer im Raum 9-133 anschließen.`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

const ids: Record<string, string> = {};

async function fresh(browser: Browser, viewport?: { width: number; height: number }): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE', viewport });
  return context.newPage();
}

async function feedItem(id: string): Promise<Record<string, any> | undefined> {
  const anonymous: APIRequestContext = await request.newContext({ baseURL: BASE_URL });
  const body = await (await anonymous.get('/api/public/feed/events?limit=500')).json();
  await anonymous.dispose();
  return body.items.find((i: { id: string }) => i.id === id);
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, 'horizontal scroll').toBeLessThanOrEqual(0);
}

test('organizer-fsi: draft, howto, poster by drop, publish: the feed carries the image', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['with'] = await createDossier(page, title('Mit Bild'));
  await expect(page.locator('app-dossier-head app-status-text', { hasText: 'Entwurf' }).first()).toBeVisible();
  await expect(page.locator('app-poster-slot').getByText('Ohne Bild nicht bewerbbar')).toBeVisible();
  await setSummary(page, 'Film, Popcorn und Diskussion');

  await toSection(page, 'Anleitung');
  await page.getByRole('button', { name: 'Vorlage einfügen' }).click();
  await page.getByRole('textbox', { name: 'Diese Ausgabe' }).fill(HOWTO);
  await page.getByRole('button', { name: 'Als neue Fassung speichern' }).click();
  await page.getByRole('button', { name: 'Fassung speichern' }).click();
  await expect(page.getByText('Neue Fassung gespeichert.')).toBeVisible();

  await uploadPoster(page, { viaDrop: true, altText: 'Plakat der Movienight', credit: 'Fachschaft Informatik' });
  await waitForCleanPoster(page, ids['with']);
  await page.reload();
  await expect(page.locator('app-poster-slot img')).toBeVisible();

  await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
  const item = await feedItem(ids['with']);
  expect(item?.['title']).toBe(title('Mit Bild'));
  expect(item?.['image']).toMatchObject({ alt: 'Plakat der Movienight', credit: 'Fachschaft Informatik' });
  await page.context().close();
});

test('organizer-fsi: an event without a poster goes out with a banner, the feed says image null', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['without'] = await createDossier(page, title('Ohne Bild'));
  await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
  await expect(page.getByRole('status').filter({ hasText: 'Ohne Bild nicht bewerbbar' })).toBeVisible();
  const item = await feedItem(ids['without']);
  expect(item).toBeTruthy();
  expect(item?.['image']).toBeNull();

  await page.goto(`/dossiers?q=${encodeURIComponent(title('Ohne Bild'))}`);
  const card = page.getByRole('article').filter({ hasText: title('Ohne Bild') });
  await expect(card.getByText('Ohne Bild', { exact: true })).toBeVisible();
  await page.context().close();
});

test('an archived event is the template of a new draft with the copied howto', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  await page.goto(`/dossiers/${ids['with']}`);
  await runAction(page, 'Archivieren', 'Archiv');

  await page.goto(`/archiv?q=${encodeURIComponent(title('Mit Bild'))}`);
  const hit = page.getByRole('article', { name: title('Mit Bild') });
  await hit.getByRole('button', { name: 'Neu aus Vorlage' }).click();
  const dialog = page.getByRole('dialog', { name: 'Neu aus Vorlage' });
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).fill('01.03.2099');
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).fill('19:30');
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).blur();
  await dialog.getByRole('button', { name: 'Neu anlegen' }).click();
  await page.waitForURL(/\/dossiers\/[0-9a-f-]{36}$/);
  ids['clone'] = page.url().split('/').pop() as string;

  expect((await eventOf(page, ids['clone']))['state']).toBe('draft');
  await toSection(page, 'Anleitung');
  await expect(page.getByRole('textbox', { name: 'Diese Ausgabe' })).toHaveValue(new RegExp(`Anleitung ${STAMP}`));
  await page.context().close();
});

test('cancel stays in the feed, unpublish removes the event, the editor restores an archived one', async ({ browser }) => {
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  await organizer.goto(`/dossiers/${ids['without']}`);
  await organizer.getByRole('group', { name: 'Aktionen' }).getByRole('button', { name: 'Absagen' }).click();
  const dialog = organizer.getByRole('dialog', { name: 'Event absagen' });
  await dialog.getByRole('combobox', { name: /Öffentlicher Grund/ }).click();
  await organizer.getByRole('option', { name: 'Krankheit' }).click();
  await expectNoAxeViolations(organizer, 'cancel dialog', '[role="dialog"]');
  await dialog.getByRole('button', { name: 'Absagen' }).last().click();
  await expect(organizer.locator('app-dossier-head').getByText('Abgesagt').first()).toBeVisible();
  expect((await feedItem(ids['without']))?.['status']).toBe('cancelled');

  await runAction(organizer, 'Zurückziehen', 'Entwurf');
  expect(await feedItem(ids['without'])).toBeUndefined();
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${ids['with']}`);
  await runAction(editor, 'Wiederherstellen', 'Entwurf');
  expect(await feedItem(ids['with'])).toBeUndefined();
  await editor.context().close();
});

test('the dossier page and the list pass axe in light and dark, desktop and 360 px', async ({ browser }) => {
  test.setTimeout(150_000);
  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 360, height: 740 },
  ]) {
    const page = await fresh(browser, viewport);
    await login(page, 'organizer-fsi');
    await page.goto(`/dossiers/${ids['without']}`);
    await expect(page.getByRole('heading', { level: 1, name: title('Ohne Bild') })).toBeVisible();
    await noHorizontalScroll(page);
    await expectNoAxeViolations(page, `dossier (${viewport.width})`);

    await page.goto('/dossiers');
    await expect(page.getByRole('heading', { level: 1, name: 'Events' })).toBeVisible();
    await noHorizontalScroll(page);
    await expectNoAxeViolations(page, `list (${viewport.width})`);

    await page.getByRole('radio', { name: 'Kalender' }).click();
    await expect(page.getByLabel('Termine im Kalender').or(page.getByLabel('Termine nach Tagen')).first()).toBeVisible();
    await noHorizontalScroll(page);
    await expectNoAxeViolations(page, `calendar (${viewport.width})`);
    await page.context().close();
  }
});
