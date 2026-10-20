/**
 * M3 acceptance (PLAN 16.1, row M3) against the compose stack with the Keycloak dev IdP: the board by keyboard and
 * on the phone, four-eyes, the field classes in `live`, cancellation in the public feed, autosave with its edit
 * conflict, a proposal by a member, and axe in light and dark.
 */
import {
  type APIRequestContext,
  type Browser,
  type Page,
  expect,
  request,
  test,
} from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { confirmTransition, createDossier, setSummary, uploadPoster } from './support/dossier';
import { eventOf, login, patchEvent, postJson, waitForCleanPoster } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const title = (name: string): string => `E2E M3 ${name} ${STAMP}`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

const ids: Record<string, string> = {};

async function fresh(
  browser: Browser,
  viewport?: { width: number; height: number },
): Promise<Page> {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    locale: 'de-DE',
    ...(viewport && { viewport, hasTouch: true }),
  });
  return context.newPage();
}

async function liveRegion(page: Page): Promise<string> {
  const texts = await page
    .locator('p[aria-live="polite"], p[aria-live="assertive"]')
    .allTextContents();
  return texts.join(' ');
}

/** The board filtered to the dossier of this run: a column shows only its first cards, the dev DB has many. */
function boardOf(name: string): string {
  return `/pipeline?q=${encodeURIComponent(title(name))}`;
}

function card(page: Page, name: string) {
  return page.getByRole('button', { name: new RegExp(title(name)) }).first();
}

/** A planned dossier with summary and a scanned poster, created by organizer-fsi (state `planning`). */
async function preparePlanning(
  page: Page,
  name: string,
  org: 'fsi' | 'stupa' = 'fsi',
): Promise<string> {
  const id = await createDossier(page, title(name));
  await confirmTransition(page, 'Planung starten', 'Planung');
  await setSummary(page, `Kurztext ${name}`);
  await uploadPoster(
    page,
    'Plakat der Veranstaltung',
    org === 'fsi' ? 'Fachschaft Informatik' : 'StuPa',
  );
  await waitForCleanPoster(page, id);
  return id;
}

/** organizer-fsi prepares and requests approval, the editor approves and publishes: the dossier is `live`. */
async function prepareLive(browser: Browser, name: string): Promise<string> {
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  const id = await preparePlanning(organizer, name);
  await organizer.reload();
  await confirmTransition(organizer, 'Freigabe anfragen', 'Freigabe');
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${id}`);
  await confirmTransition(editor, 'Freigeben', 'Freigegeben');
  await confirmTransition(editor, 'Veröffentlichen', 'Veröffentlicht');
  await editor.context().close();
  return id;
}

test('Board: keyboard drag from idea to planning, back with Escape, no drop into a closed column', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['board'] = await createDossier(page, title('Board'));
  await page.goto(boardOf('Board'));

  const board = card(page, 'Board');
  await expect(board).toBeVisible();
  await board.focus();
  await page.keyboard.press('Space');
  await expect(board).toHaveAttribute('aria-pressed', 'true');
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => liveRegion(page)).toContain('Spalte Planung, Verschieben möglich.');
  await page.keyboard.press('Space');
  await expect
    .poll(() => liveRegion(page))
    .toContain(`„${title('Board')}“ nach Planung verschoben.`);
  expect((await eventOf(page, ids['board']))['state']).toBe('planning');
  // The board reloads after the move; lifting the old element would lose focus on the re-render.
  await expect(
    page.locator('[data-col="planning"]').getByRole('button', { name: new RegExp(title('Board')) }),
  ).toBeVisible();

  await card(page, 'Board').focus();
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Escape');
  await expect.poll(() => liveRegion(page)).toContain('zurückgelegt');

  await card(page, 'Board').focus();
  await page.keyboard.press('Space');
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight');
  await expect.poll(() => liveRegion(page)).toContain('Spalte Nachbereitung, nicht möglich.');
  await page.keyboard.press('Space');
  await expect.poll(() => liveRegion(page)).toContain('nicht möglich');
  await page.keyboard.press('Escape');

  await card(page, 'Board').focus();
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Space');
  const dialog = page.getByRole('dialog', { name: 'Freigabe anfragen' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: 'Fehlt noch' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  await page.context().close();
});

test('Phone: tabs, swipe and the move sheet by long press', async ({ browser }) => {
  const page = await fresh(browser, { width: 390, height: 844 });
  await login(page, 'organizer-fsi');
  await page.goto(boardOf('Board'));
  await expect(page.getByRole('tab', { name: /Idee/ })).toBeVisible();
  await page.getByRole('tab', { name: /Planung/ }).click();
  await expect(page.getByRole('tab', { name: /Planung/ })).toHaveAttribute('aria-selected', 'true');

  await page
    .locator('.bv__pager')
    .evaluate((el) => el.scrollTo({ left: el.clientWidth * 2, behavior: 'instant' }));
  await expect(page.getByRole('tab', { name: /Freigabe/ })).toHaveAttribute(
    'aria-selected',
    'true',
  );

  await page.getByRole('tab', { name: /Planung/ }).click();
  await expect
    .poll(() =>
      page.locator('.bv__pager').evaluate((el) => Math.round(el.scrollLeft - el.clientWidth)),
    )
    .toBe(0);
  await page.waitForTimeout(500);
  const target = card(page, 'Board');
  await expect(target).toBeVisible();
  await target.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const box = (await target.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 20);
  await page.mouse.down();
  await page.waitForTimeout(700);
  await page.mouse.up();
  const sheet = page.getByRole('dialog', { name: 'Verschieben' });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole('button', { name: 'Freigabe anfragen' })).toBeVisible();
  await expectNoAxeViolations(page, 'move sheet', '[role="dialog"]');
  await sheet.getByRole('button', { name: 'Schließen' }).click();
  await expect(sheet).toBeHidden();
  await expectNoAxeViolations(page, 'pipeline on the phone');
  await page.context().close();
});

test('Four eyes: the submitter cannot approve, a second approver can', async ({ browser }) => {
  const first = await fresh(browser);
  await login(first, 'approver-stupa');
  ids['fourEyes'] = await preparePlanning(first, 'Vier-Augen', 'stupa');
  await first.reload();
  await confirmTransition(first, 'Freigabe anfragen', 'Freigabe');

  await first.getByRole('button', { name: 'Freigeben' }).click();
  const dialog = first.getByRole('dialog', { name: 'Freigeben' });
  await expect(
    dialog.getByText('Du hast dieses Event eingereicht. Eine andere Person muss freigeben.'),
  ).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Schließen' }).click();
  const refused = await postJson(first, `/api/events/${ids['fourEyes']}/transitions/T04`);
  expect(refused.status()).toBe(403);
  expect((await refused.json()).code).toBe('four_eyes');
  await first.context().close();

  const second = await fresh(browser);
  await login(second, 'approver2-stupa');
  await second.goto(`/dossiers/${ids['fourEyes']}`);
  await confirmTransition(second, 'Freigeben', 'Freigegeben');
  expect((await eventOf(second, ids['fourEyes']))['state']).toBe('approved');
  await second.context().close();
});

test('Field classes in live: the organizer corrects the summary, the time stays with the editorial staff', async ({
  browser,
}) => {
  ids['live'] = await prepareLive(browser, 'Live');
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  await organizer.goto(`/dossiers/${ids['live']}`);
  const before = (await eventOf(organizer, ids['live']))['summary'];

  await expect(organizer.getByRole('textbox', { name: /Beginn, Uhrzeit/ })).toBeDisabled();
  await expect(organizer.getByText('Nur über die Redaktion änderbar.').first()).toBeVisible();
  await setSummary(organizer, 'Korrigierter Kurztext');

  const live = await eventOf(organizer, ids['live']);
  const locked = await patchEvent(organizer, ids['live'], live['rev'], {
    startsAt: live['endsAt'],
  });
  expect(locked.status()).toBe(409);
  expect((await locked.json()).code).toBe('field_locked');
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto('/aufgaben');
  await expect(editor.getByRole('heading', { name: 'Nachträglich geändert' })).toBeVisible();
  await editor.getByRole('link', { name: title('Live') }).click();
  await expect(editor.getByRole('heading', { level: 1, name: title('Live') })).toBeVisible();
  await editor.getByRole('button', { name: 'Zurücksetzen' }).click();
  await editor
    .getByRole('dialog')
    .getByRole('button', { name: /zurücksetzen/i })
    .click();
  await expect.poll(async () => (await eventOf(editor, ids['live']))['summary']).toBe(before);

  const time = editor.getByRole('textbox', { name: /Beginn, Uhrzeit/ });
  await expect(time).toBeEnabled();
  await time.fill('20:15');
  await time.blur();
  await editor.getByRole('button', { name: 'Speichern' }).click();
  await expect(editor.getByText('Gespeichert.')).toBeVisible();
  expect((await eventOf(editor, ids['live']))['startsAt']).not.toBe(live['startsAt']);
  await editor.context().close();
});

test('Cancellation stays in the feed as cancelled and the editor takes it back', async ({
  browser,
}) => {
  const organizer = await fresh(browser);
  await login(organizer, 'organizer-fsi');
  await organizer.goto(`/dossiers/${ids['live']}`);
  await organizer.getByRole('button', { name: 'Mehr' }).click();
  await organizer.getByRole('menuitem', { name: 'Absagen oder verschieben' }).click();
  const dialog = organizer.getByRole('dialog', { name: 'Absagen oder verschieben' });
  await dialog.getByRole('textbox', { name: /Grund \(intern\)/ }).fill('Referent krank');
  await dialog.getByRole('combobox', { name: /Öffentlicher Grund/ }).click();
  await organizer.getByRole('option', { name: 'Krankheit' }).click();
  await dialog.getByRole('button', { name: 'Absagen' }).last().click();
  await expect(organizer.locator('app-dossier-head').getByText(/Abgesagt/)).toBeVisible();

  const anonymous: APIRequestContext = await request.newContext({ baseURL: BASE_URL });
  const feed = await (await anonymous.get('/api/public/feed/events')).json();
  const item = feed.items.find((i: { id: string }) => i.id === ids['live']);
  expect(item).toBeTruthy();
  expect(item.status).toBe('cancelled');
  expect(JSON.stringify(item)).not.toContain('Referent krank');
  await anonymous.dispose();

  await organizer.goto(boardOf('Live'));
  await expect(card(organizer, 'Live')).toContainText('Abgesagt');
  await organizer.context().close();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${ids['live']}`);
  await editor.getByRole('button', { name: 'Mehr' }).click();
  await editor.getByRole('menuitem', { name: 'Absage zurücknehmen' }).click();
  await editor
    .getByRole('textbox', { name: /Warum nimmst du die Absage zurück/ })
    .fill('Termin steht wieder');
  await editor.getByRole('dialog').getByRole('button', { name: 'Absage zurücknehmen' }).click();
  await expect(editor.locator('app-dossier-head').getByText(/Abgesagt/)).toBeHidden();
  await editor.context().close();
});

test('Autosave survives a reload, and a second save raises the edit conflict', async ({
  browser,
}) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  ids['autosave'] = await createDossier(page, title('Autosave'));
  await confirmTransition(page, 'Planung starten', 'Planung');
  const summary = page.getByRole('textbox', { name: /Kurztext/ });
  await summary.fill('Nur als Entwurf');
  await expect(page.locator('app-autosave-indicator')).toContainText(/Gespeichert \d\d:\d\d/, {
    timeout: 25_000,
  });

  await page.reload();
  await expect(page.getByRole('textbox', { name: /Kurztext/ })).toHaveValue('Nur als Entwurf');
  await expect(page.getByText(/Entwurf von \d\d:\d\d wiederhergestellt\./)).toBeVisible();

  const other = await fresh(browser);
  await login(other, 'organizer-fsi');
  await other.goto(`/dossiers/${ids['autosave']}`);
  await other.getByRole('textbox', { name: /Kurztext/ }).fill('Von der zweiten Sitzung');
  await other.getByRole('button', { name: 'Speichern' }).click();
  await expect(other.getByText('Gespeichert.')).toBeVisible();

  await page.getByRole('textbox', { name: /Kurztext/ }).fill('Nur als Entwurf, weiter getippt');
  const conflict = page.getByRole('dialog', { name: 'Jemand anderes war schneller' });
  await expect(conflict).toBeVisible({ timeout: 25_000 });
  await expect(conflict.getByText('Ausgangsstand')).toBeVisible();
  await expect(conflict.getByText('Deins', { exact: true })).toBeVisible();
  await expect(conflict.getByText('Neu', { exact: true })).toBeVisible();
  await expectNoAxeViolations(page, 'conflict dialog');
  await conflict.getByRole('button', { name: 'Neu laden, meine Änderungen verwerfen' }).click();
  await expect(page.getByRole('textbox', { name: /Kurztext/ })).toHaveValue(
    'Von der zweiten Sitzung',
  );
  await other.context().close();
  await page.context().close();
});

test('Proposal: a member proposes, the editor assigns an organization, the member loses sight of it', async ({
  browser,
}) => {
  const member = await fresh(browser);
  await login(member, 'member');
  await member.goto('/aufgaben');
  await member.getByRole('button', { name: 'Neues Event' }).first().click();
  const dialog = member.getByRole('dialog', { name: 'Event vorschlagen' });
  await expect(dialog.getByRole('textbox', { name: 'Organisation' })).toBeDisabled();
  await expectNoAxeViolations(member, 'proposal dialog');
  await dialog.getByRole('textbox', { name: 'Titel', exact: true }).fill(title('Vorschlag'));
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).fill('01.12.2099');
  await dialog.getByRole('textbox', { name: 'Beginn, Datum' }).blur();
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).fill('19:30');
  await dialog.getByRole('textbox', { name: 'Beginn, Uhrzeit' }).blur();
  await dialog.getByRole('button', { name: 'Anlegen' }).click();
  await member.waitForURL(/\/dossiers\/[0-9a-f-]{36}$/);
  ids['proposal'] = member.url().split('/').pop() as string;

  await member.goto('/aufgaben');
  await expect(member.getByRole('heading', { name: 'Meine Dossiers' })).toBeVisible();
  await expect(member.getByRole('link', { name: title('Vorschlag') })).toBeVisible();

  const editor = await fresh(browser);
  await login(editor, 'editor');
  await editor.goto(`/dossiers/${ids['proposal']}`);
  await editor.getByRole('button', { name: 'Mehr' }).click();
  await editor.getByRole('menuitem', { name: 'Organisation zuweisen' }).click();
  const assign = editor.getByRole('dialog', { name: 'Organisation zuweisen' });
  await assign.getByRole('combobox', { name: /Organisation/ }).click();
  await editor.getByRole('option', { name: 'Fachschaft Informatik' }).click();
  await assign.getByRole('button', { name: 'Zuweisen' }).click();
  await expect(editor.getByText('Organisation zugewiesen.')).toBeVisible();
  await editor.context().close();

  expect((await member.request.get(`/api/events/${ids['proposal']}`)).status()).toBe(404);
  await member.context().close();
});

test('axe: the pages and dialogs have no serious or critical finding in light and dark', async ({
  browser,
}) => {
  test.setTimeout(150_000);
  const editor = await fresh(browser);
  await login(editor, 'editor');
  for (const path of ['/aufgaben', '/pipeline', '/dossiers']) {
    await editor.goto(path);
    await editor.getByRole('heading', { level: 1 }).first().waitFor();
    await expectNoAxeViolations(editor, path);
  }

  await editor.goto('/aufgaben');
  await editor.getByRole('button', { name: 'Neues Event' }).first().click();
  await expectNoAxeViolations(editor, 'I05');
  await editor.keyboard.press('Escape');

  for (const [name, id] of [
    ['planning', ids['autosave']],
    ['in_review', ids['fourEyes']],
    ['live', ids['live']],
  ] as const) {
    await editor.goto(`/dossiers/${id}`);
    await editor.getByRole('heading', { level: 1, name: new RegExp(`E2E M3`) }).waitFor();
    await expectNoAxeViolations(editor, `dossier in ${name}`);
  }

  await editor.goto(`/dossiers/${ids['autosave']}`);
  await editor.getByRole('button', { name: 'Freigabe anfragen' }).click();
  await expectNoAxeViolations(editor, 'I13');
  await editor.keyboard.press('Escape');
  await editor.getByRole('button', { name: 'Mehr' }).click();
  await editor.getByRole('menuitem', { name: 'Ausnahme ohne Bild' }).click();
  await expectNoAxeViolations(editor, 'I15');
  await editor.keyboard.press('Escape');

  await editor.goto(`/dossiers/${ids['live']}`);
  await editor.getByRole('button', { name: 'Mehr' }).click();
  await editor.getByRole('menuitem', { name: 'Absagen oder verschieben' }).click();
  await expectNoAxeViolations(editor, 'I14');
  await editor.context().close();

  const phone = await fresh(browser, { width: 390, height: 844 });
  await login(phone, 'editor');
  await phone.goto('/pipeline');
  await phone.getByRole('tab').first().waitFor();
  await expectNoAxeViolations(phone, '/pipeline on the phone');
  await phone.context().close();
});
