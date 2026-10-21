/**
 * M5 acceptance in the browser (contract 12.3 l): a new edition from an archived Movienight (preview, no poster), the search
 * finds "Sitzung" for "Fachschaftssitzung", the palette by keyboard, the calendar by keyboard, the follow-up up to T09 and the
 * archive, the library and the formats, at 360 px and at desktop width, with axe in light and dark.
 * It needs the M5 backend (migration `0006`) and, for the clone, the Movienight fixture in the dev seed (organization FSI).
 * The follow-up test moves a dossier into `followup` with SQL (`support/db.ts`, dev stack only).
 */
import { type Browser, type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { createDossier } from './support/dossier';
import { databaseReachable, moveToFollowup } from './support/db';
import { eventOf, inDays, login } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const title = (name: string): string => `E2E M5 ${name} ${STAMP}`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

const ids: Record<string, string> = {};

async function fresh(
  browser: Browser,
  viewport?: { width: number; height: number },
): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE', viewport });
  return context.newPage();
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow, 'horizontal scroll').toBeLessThanOrEqual(0);
}

async function fillStart(
  page: Page,
  scope: ReturnType<Page['getByRole']>,
  days: number,
): Promise<void> {
  await scope.getByRole('textbox', { name: 'Beginn, Datum' }).fill(inDays(days));
  await scope.getByRole('textbox', { name: 'Beginn, Datum' }).blur();
  await scope.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).fill('19:30');
  await scope.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).blur();
}

test('a new edition from an archived Movienight: preview, no poster, "Letztes Mal"', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  await page.goto('/archiv?q=Movienight');
  const hit = page.getByRole('article').first();
  const listed = await hit.waitFor({ state: 'visible', timeout: 10_000 }).then(
    () => true,
    () => false,
  );
  test.skip(!listed, 'the Movienight fixture is not in the dev seed');
  await hit.getByRole('button', { name: 'Neu aus Vorlage' }).click();

  const dialog = page.getByRole('dialog', { name: 'Neu aus Vorlage' });
  await expect(dialog.getByText('Poster: Datum im Bild, bitte neu gestalten')).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Letztes Mal' })).toBeVisible();
  await expectNoAxeViolations(page, 'Neu aus Vorlage');

  await dialog.getByRole('button', { name: 'Neu anlegen' }).click();
  await expect(dialog.getByText('Neues Datum fehlt.')).toBeVisible();
  await fillStart(page, dialog, 60);
  await dialog.getByRole('button', { name: 'Neu anlegen' }).click();
  await page.waitForURL(/\/dossiers\/[0-9a-f-]{36}$/);
  ids['clone'] = page.url().split('/').pop() as string;

  await expect(page.getByText('Noch kein Poster hochgeladen.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Letztes Mal' })).toBeVisible();
  const event = await eventOf(page, ids['clone']);
  expect(event['state']).toBe('idea');
  expect(event['poster']).toBeNull();
  expect(event['imageException']).toBeNull();
  expect(event['derivedFromId']).toBeTruthy();
  await page.context().close();
});

test('"Fachschaftssitzung" finds "Sitzung" in the archive search', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['sitzung'] = await createDossier(page, title('Sitzung'));
  await page.goto('/archiv?status=alle');
  const field = page.getByRole('searchbox', { name: 'Archiv durchsuchen' });
  await expect(page.getByText('Suche nach Titel, Ort, Anleitung …').first()).toBeVisible();
  await field.fill('Fachschaftssitzung');
  const hit = page.getByRole('article', { name: title('Sitzung') });
  await expect(hit).toBeVisible();
  await expect(hit.locator('mark').first()).toBeVisible();
  await expectNoAxeViolations(page, 'Archiv mit Treffern');

  await field.fill('x'.repeat(100));
  await expect(field).toHaveAttribute('maxlength', '100');
  await field.fill('Kinabnd');
  await expect(
    page.getByText(/Nichts gefunden für „Kinabnd“|Kinoabend|Treffer/).first(),
  ).toBeVisible();
  await page.context().close();
});

test('the palette works with the keyboard alone', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  await page.goto('/aufgaben');
  await expect(page.getByRole('heading', { name: 'Meine Aufgaben', level: 1 })).toBeVisible();
  await page.keyboard.press('Control+k');
  const box = page.getByRole('combobox', { name: 'Dossiers, Formate, Aktionen und Seiten suchen' });
  await expect(box).toBeFocused();
  await expect(page.getByRole('group', { name: 'Navigation' })).toBeVisible();
  await expectNoAxeViolations(page, 'Palette');

  await page.keyboard.type('Archiv');
  await expect(page.getByRole('option', { name: 'Archiv', exact: true })).toBeVisible();
  await page.keyboard.press('Enter');
  await page.waitForURL(/\/archiv$/);

  await page.keyboard.press('Control+k');
  await expect(box).toBeFocused();
  await page.keyboard.type(title('Sitzung'));
  const option = page.getByRole('option', { name: new RegExp(title('Sitzung')) });
  await expect(option).toBeVisible();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('Enter');
  await page.waitForURL(new RegExp(`/dossiers/${ids['sitzung']}$`));

  await page.keyboard.press('Control+k');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Suchen und springen' })).toBeHidden();
  await page.context().close();
});

test('the calendar: month grid by keyboard, a click opens the dossier, agenda list at 360 px', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  const event = await eventOf(page, ids['sitzung']);
  const day = new Date(event['startsAt'] as string).toLocaleDateString('en-CA', {
    timeZone: 'Europe/Berlin',
  });
  await page.goto('/kalender');
  await expect(page.getByRole('grid', { name: 'Termine im Kalender' })).toBeVisible();
  const cell = page.locator(`[role="gridcell"][data-day="${day}"]`);
  for (let i = 0; i < 4; i++) {
    const shown = await cell.waitFor({ state: 'attached', timeout: 3_000 }).then(
      () => true,
      () => false,
    );
    if (shown) break;
    await page.getByRole('button', { name: 'Weiter', exact: true }).click();
  }
  await expect(cell).toHaveCount(1);
  await cell.focus();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowLeft');
  await expect(cell).toBeFocused();
  await expectNoAxeViolations(page, 'Kalender Monat', '[role="grid"]');
  await page.keyboard.press('Enter');
  const sheet = page.getByRole('dialog');
  if (await sheet.isVisible().catch(() => false))
    await sheet.getByRole('button', { name: new RegExp(title('Sitzung')) }).click();
  await page.waitForURL(new RegExp(`/dossiers/${ids['sitzung']}$`));

  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto('/kalender');
  await expect(page.getByRole('grid')).toHaveCount(0);
  await noHorizontalScroll(page);
  await page.getByRole('button', { name: 'Mehr', exact: true }).click();
  await expect(
    page.getByRole('dialog', { name: 'Mehr' }).getByRole('link', { name: 'Bibliothek' }),
  ).toBeVisible();
  await page.context().close();
});

test('the follow-up: guard list, retrospective and result, T09 to the archive', async ({
  browser,
}) => {
  test.skip(!databaseReachable(), 'the dev Postgres container is not reachable (E2E_PG_CONTAINER)');
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['followup'] = await createDossier(page, title('Nachbereitung'));
  moveToFollowup(ids['followup']);

  await page.goto(`/dossiers/${ids['followup']}/nachbereitung`);
  await expect(page.getByRole('heading', { name: 'Zum Abschließen fehlt noch' })).toBeVisible();
  await expect(page.getByText('Die Nachbereitung fehlt.')).toBeVisible();
  await expect(page.getByText('Das Ergebnis fehlt.')).toBeVisible();
  await expectNoAxeViolations(page, 'Nachbereitung');

  await page.getByRole('button', { name: 'Rückblick schreiben' }).click();
  await page.getByRole('button', { name: 'Rückblick speichern' }).click();
  await expect(page.getByText('Gespeichert.').first()).toBeVisible();

  await page.getByRole('button', { name: 'Ergebnis eintragen' }).click();
  await page.getByRole('spinbutton', { name: 'Besucher:innen' }).fill('12');
  await page.getByRole('textbox', { name: /Kosten \(Ist\)/ }).fill('0');
  await page.getByRole('textbox', { name: /Kosten \(Ist\)/ }).blur();
  await page.getByRole('button', { name: 'Ergebnis speichern' }).click();
  await expect(page.getByText('Ergebnis gespeichert.')).toBeVisible();

  await expect(page.getByText('Alles bereit.')).toBeVisible();
  await page.getByRole('button', { name: 'Nachbereitung abschließen' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Nachbereitung abschließen' });
  await dialog.getByRole('button', { name: 'Bestätigen', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('app-status-text', { hasText: 'Archiv' }).first()).toBeVisible();
  expect((await eventOf(page, ids['followup']))['state']).toBe('archived');
  await page.context().close();
});

test('archive, formats and library render at desktop and 360 px, light and dark, without horizontal scroll', async ({
  browser,
}) => {
  for (const viewport of [
    { width: 1280, height: 800 },
    { width: 360, height: 740 },
  ]) {
    const page = await fresh(browser, viewport);
    await login(page, 'organizer-fsi');
    for (const [path, heading] of [
      ['/archiv', 'Archiv'],
      ['/formate', 'Formate'],
      ['/bibliothek', 'Bibliothek'],
      ['/kalender', 'Kalender'],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
      await noHorizontalScroll(page);
      await expectNoAxeViolations(page, `${heading} (${viewport.width})`);
    }
    await page.context().close();
  }
});

test('a format page: the howto tab, the editions and the way to a new edition', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  const response = await page.request.get('/api/formats/movienight');
  test.skip(response.status() !== 200, 'the format "movienight" is not in the dev seed');
  await page.goto('/formate/movienight');
  await expect(page.getByRole('heading', { name: 'Movienight' }).first()).toBeVisible();
  await page.getByRole('tab', { name: /Ausgaben/ }).click();
  await expect(
    page.locator('app-format-editions').or(page.getByText('Noch keine Ausgabe dieses Formats.')),
  ).toBeVisible();
  await expectNoAxeViolations(page, 'Format Ausgaben');
  await page.getByRole('button', { name: 'Neue Ausgabe' }).first().click();
  await expect(page.getByRole('dialog', { name: /Neu aus Vorlage|Neue Ausgabe/ })).toBeVisible();
  await page.context().close();
});

test('a dossier can be saved as a format from the palette', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  await page.goto(`/dossiers/${ids['sitzung']}`);
  await expect(page.getByRole('heading', { level: 1, name: title('Sitzung') })).toBeVisible();
  await page.keyboard.press('Control+k');
  await expect(
    page.getByRole('combobox', { name: 'Dossiers, Formate, Aktionen und Seiten suchen' }),
  ).toBeFocused();
  await page.keyboard.type('Als Format');
  await page.getByRole('option', { name: 'Als Format speichern' }).click();
  const dialog = page.getByRole('dialog', { name: 'Als Format speichern' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('textbox', { name: /Kürzel/ })).toHaveValue(/e2e-m5-sitzung/);
  await dialog.getByRole('button', { name: 'Abbrechen' }).click();
  await page.context().close();
});
