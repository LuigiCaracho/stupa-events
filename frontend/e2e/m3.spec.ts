/**
 * M3 acceptance, cut down by M5b: the dossier page edits like one form in every state (no field classes), autosave survives a
 * reload and a second save raises the edit conflict, an archived dossier locks its key data, the anchor navigation works on
 * the phone, and a member who may not create events gets the note instead of a form. Axe in light and dark.
 */
import { type Browser, type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { createDossier, runAction, setSummary, toSection } from './support/dossier';
import { eventOf, login } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const title = (name: string): string => `E2E M3 ${name} ${STAMP}`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

const ids: Record<string, string> = {};

async function fresh(browser: Browser, viewport?: { width: number; height: number }): Promise<Page> {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    locale: 'de-DE',
    ...(viewport && { viewport, hasTouch: true }),
  });
  return context.newPage();
}

async function openBasics(page: Page): Promise<void> {
  const toggle = page.getByRole('button', { name: /^Eckdaten/ });
  if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click();
}

test('published: the organizer corrects summary and time in the same form', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['live'] = await createDossier(page, title('Veröffentlicht'));
  await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
  await openBasics(page);
  await setSummary(page, 'Korrigierter Kurztext');

  const before = await eventOf(page, ids['live']);
  const time = page.getByRole('textbox', { name: /Beginn, Uhrzeit/ });
  await expect(time).toBeEnabled();
  await time.fill('20:15');
  await time.blur();
  await page.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();
  expect((await eventOf(page, ids['live']))['startsAt']).not.toBe(before['startsAt']);
  await page.context().close();
});

test('archived: the key data are locked until the editor restores the dossier', async ({ browser }) => {
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  await organizer.goto(`/dossiers/${ids['live']}`);
  await runAction(organizer, 'Archivieren', 'Archiv');
  await openBasics(organizer);
  await expect(organizer.getByText(/Im Archiv lassen sich die Eckdaten nicht mehr ändern/)).toBeVisible();
  await expect(organizer.getByRole('textbox', { name: /Kurztext/ })).toHaveCount(0);
  await expect(organizer.getByRole('button', { name: 'Wiederherstellen' })).toHaveCount(0);
  await expectNoAxeViolations(organizer, 'archived dossier');
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${ids['live']}`);
  await runAction(editor, 'Wiederherstellen', 'Entwurf');
  await editor.context().close();
});

test('autosave survives a reload, and a second save raises the edit conflict', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['autosave'] = await createDossier(page, title('Autosave'));
  const summary = page.getByRole('textbox', { name: /Kurztext/ });
  await summary.fill('Nur als Entwurf');
  await expect(page.locator('app-autosave-indicator')).toContainText(/Gespeichert \d\d:\d\d/, { timeout: 25_000 });

  await page.reload();
  await expect(page.getByRole('textbox', { name: /Kurztext/ })).toHaveValue('Nur als Entwurf');
  await expect(page.getByText(/Entwurf von \d\d:\d\d wiederhergestellt\./)).toBeVisible();

  const other = await fresh(browser);
  await login(other, 'organizer-fsi');
  await other.goto(`/dossiers/${ids['autosave']}`);
  await other.getByRole('textbox', { name: /Kurztext/ }).fill('Von der zweiten Sitzung');
  await other.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(other.getByText('Gespeichert.')).toBeVisible();

  await page.getByRole('textbox', { name: /Kurztext/ }).fill('Nur als Entwurf, weiter getippt');
  const conflict = page.getByRole('dialog', { name: 'Jemand anderes war schneller' });
  await expect(conflict).toBeVisible({ timeout: 25_000 });
  await expect(conflict.getByText('Ausgangsstand')).toBeVisible();
  await expect(conflict.getByText('Deins', { exact: true })).toBeVisible();
  await expect(conflict.getByText('Neu', { exact: true })).toBeVisible();
  await expectNoAxeViolations(page, 'conflict dialog');
  await conflict.getByRole('button', { name: 'Neu laden, meine Änderungen verwerfen' }).click();
  await expect(page.getByRole('textbox', { name: /Kurztext/ })).toHaveValue('Von der zweiten Sitzung');
  await other.context().close();
  await page.context().close();
});

test('phone: the anchor navigation jumps to a section, no side scroll, axe', async ({ browser }) => {
  const page = await fresh(browser, { width: 390, height: 844 });
  await login(page, 'organizer-fsi');
  await page.goto(`/dossiers/${ids['autosave']}`);
  await expect(page.getByRole('heading', { level: 1, name: title('Autosave') })).toBeVisible();
  await toSection(page, 'Checkliste');
  await expect(page.getByRole('heading', { name: /^Checkliste/ })).toBeInViewport();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  await expectNoAxeViolations(page, 'dossier on the phone');
  await page.context().close();
});

test('a member who may not create events gets the note instead of the form', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'member');
  await page.goto('/dossiers');
  await page.getByRole('button', { name: 'Neues Event' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Neues Event' });
  await expect(dialog.getByText('Für dich ist keine Organisation freigeschaltet.')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Anlegen' })).toBeDisabled();
  await expectNoAxeViolations(page, 'new event without organization');
  await page.context().close();
});

test('axe: list, new-event dialog and cancel dialog have no serious finding', async ({ browser }) => {
  test.setTimeout(150_000);
  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto('/dossiers');
  await editor.getByRole('heading', { level: 1, name: 'Events' }).waitFor();
  await expectNoAxeViolations(editor, '/dossiers');
  await editor.getByRole('button', { name: 'Neues Event' }).first().click();
  await expectNoAxeViolations(editor, 'new event dialog');
  await editor.keyboard.press('Escape');
  await editor.goto(`/dossiers/${ids['autosave']}`);
  await runAction(editor, 'Veröffentlichen', 'Veröffentlicht');
  await editor.getByRole('group', { name: 'Aktionen' }).getByRole('button', { name: 'Verschieben' }).click();
  await expectNoAxeViolations(editor, 'postpone dialog');
  await editor.context().close();
});
