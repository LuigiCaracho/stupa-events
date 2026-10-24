/**
 * B3 acceptance in the browser (contract 8.3): Get started to a profile calendar that holds only the chosen
 * categories; the mail path with the double opt-in (a GET on the link confirms nothing, the button does), manage, a new
 * calendar address, delete; the same answer for a known and an unknown address; the network allowlist and axe over the
 * new pages. Mails come from Mailpit (:8025), the Listmonk checks need the dev API user (see `support/listmonk.ts`).
 * The public limit is 10 signups per hour and IP: flush the dev Redis before a second run in the same hour.
 */
import { type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { hasSubscriber } from './support/listmonk';
import { deleteAll, waitForMail } from './support/mailpit';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };
const PARTY_CATEGORIES = ['party', 'campusfest', 'festival', 'get-together'];

test.use({ baseURL: BASE_URL, locale: 'de-DE', viewport: PHONE });
test.describe.configure({ mode: 'serial' });

const stamp = (): string => `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
// The API validates addresses like a mail server would: the special-use TLD `.test` is refused.
const addressOf = (name: string): string => `${name}@example.org`;

interface Answers {
  interests: string[];
  mail?: string;
}

async function fillQuestionnaire(page: Page, answers: Answers): Promise<void> {
  await page.goto('/start');
  await expect(page.getByRole('heading', { name: 'Was interessiert dich?' })).toBeVisible();
  for (const label of answers.interests) await page.getByRole('button', { name: label }).click();
  await page.getByRole('radio', { name: 'Nein' }).click();
  await page.getByRole('button', { name: 'Weiter' }).click();
  await page.getByRole('button', { name: 'Weiter' }).click();
  if (answers.mail) {
    await page.getByRole('radio', { name: 'Kalender und Mail' }).click();
    await page.getByRole('button', { name: 'Weiter' }).click();
    await page.getByLabel('Mailadresse').fill(answers.mail);
    await page.getByRole('checkbox').check();
  }
  await page.getByRole('button', { name: 'Profil erstellen' }).click();
  await expect(page.getByRole('heading', { name: 'Dein Kalender ist fertig' })).toBeVisible();
}

const icsUrlOf = (page: Page): Promise<string> =>
  page.getByLabel('Dein Kalender-Link').inputValue();

const pathOf = (url: string): string => new URL(url).pathname;

const uidsOf = (ics: string): Set<string> =>
  new Set([...ics.matchAll(/^UID:(.+)$/gm)].map((m) => m[1].trim()));

async function uidsAt(page: Page, path: string): Promise<Set<string>> {
  const answer = await page.request.get(path);
  return answer.ok() ? uidsOf(await answer.text()) : new Set();
}

test('questionnaire to profile calendar: only parties, no meetings, no cookie', async ({
  page,
  context,
}) => {
  await fillQuestionnaire(page, { interests: ['Partys und Feiern'] });
  await expect(page.getByRole('link', { name: 'In Kalender-App öffnen' })).toHaveAttribute(
    'href',
    /^webcal:\/\/.+\/ics\/p\/[A-Za-z0-9_-]{43}\.ics$/,
  );
  const https = await icsUrlOf(page);
  expect(https).toMatch(/^https?:\/\/.+\/ics\/p\/[A-Za-z0-9_-]{43}\.ics$/);

  const answer = await page.request.get(pathOf(https));
  expect(answer.status()).toBe(200);
  expect(answer.headers()['content-type']).toContain('text/calendar');
  expect(answer.headers()['set-cookie']).toBeUndefined();
  const profile = uidsOf(await answer.text());

  const wanted = new Set<string>();
  for (const slug of PARTY_CATEGORIES)
    (await uidsAt(page, `/ics/k/${slug}.ics`)).forEach((uid) => wanted.add(uid));
  const meetings = await uidsAt(page, '/ics/k/sitzung.ics');
  for (const uid of profile)
    expect(wanted.has(uid), `${uid} belongs to a party category`).toBe(true);
  for (const uid of meetings) expect(profile.has(uid), `${uid} is a meeting`).toBe(false);
  expect(await context.cookies()).toEqual([]);
  expect(
    await page.evaluate(() => JSON.stringify({ ...sessionStorage, ...localStorage })),
  ).not.toContain(https.split('/').pop()?.replace('.ics', '') ?? 'x');
});

test('a reload of the result page starts again at step 1', async ({ page }) => {
  await fillQuestionnaire(page, { interests: ['Partys und Feiern'] });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Was interessiert dich?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Partys und Feiern' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
});

test('mail path: DOI mail, GET confirms nothing, the button does, manage, new address, delete', async ({
  page,
  browser,
}) => {
  test.setTimeout(240_000);
  const email = addressOf(stamp());
  await deleteAll();
  await fillQuestionnaire(page, { interests: ['Partys und Feiern'], mail: email });
  await expect(page.getByText('Wir haben dir eine Bestätigungsmail geschickt.')).toBeVisible();
  const oldIcs = await icsUrlOf(page);

  const doi = await waitForMail(email);
  expect(doi.path, 'confirmation link in the mail').toMatch(/^\/bestaetigen\/[A-Za-z0-9_-]{43}$/);
  const token = doi.path?.split('/').pop() ?? '';

  await page.goto(doi.path ?? '');
  await expect(page.getByRole('button', { name: 'Abo bestätigen' })).toBeVisible();
  await expect(page).toHaveURL(/\/bestaetigen$/);
  const preview = () =>
    page.request.post('/api/public/subscriptions/confirm/preview', { data: { token } });
  const first = await preview();
  expect(first.status()).toBe(200);
  expect(await (await preview()).json()).toEqual(await first.json());

  await page.getByRole('button', { name: 'Abo bestätigen' }).click();
  await expect(page.getByText('Danke, dein Abo ist aktiv.')).toBeVisible();
  const again = await page.request.post('/api/public/subscriptions/confirm', { data: { token } });
  expect(again.status()).toBe(404);

  await expect
    .poll(() => hasSubscriber(email), { timeout: 90_000, intervals: [2_000] })
    .not.toBe(false);

  await deleteAll();
  await page.goto('/abos');
  await page.getByRole('button', { name: 'Verwaltungslink anfordern' }).click();
  const ask = page.getByRole('dialog');
  await ask.getByLabel('Mailadresse').fill(email);
  await ask.getByRole('button', { name: 'Link anfordern', exact: true }).click();
  await expect(
    page.getByText('Wenn die Adresse bei uns angemeldet ist, ist der Link unterwegs.'),
  ).toBeVisible();
  const magic = await waitForMail(email);
  expect(magic.path).toMatch(/^\/abo\/[A-Za-z0-9_-]{43}$/);

  await page.goto(magic.path ?? '');
  await expect(page.getByRole('heading', { name: 'Abo verwalten' })).toBeVisible();
  await expect(page).toHaveURL(/\/abo$/);
  await page.getByRole('button', { name: 'Kino, Konzerte, Kultur' }).click();
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();

  await page.getByRole('button', { name: 'Neue URL erzeugen' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Neue URL erzeugen' }).click();
  await expect(page.getByLabel('Dein Kalender-Link')).toBeVisible();
  const newIcs = await icsUrlOf(page);
  expect(newIcs).not.toBe(oldIcs);
  expect((await page.request.get(pathOf(oldIcs))).status()).toBe(404);
  expect((await page.request.get(pathOf(newIcs))).status()).toBe(200);

  await page.getByRole('button', { name: 'Alles abbestellen und Daten löschen' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Alles abbestellen und Daten löschen' })
    .click();
  await expect(
    page.getByText('Erledigt. Wir haben deine Adresse und dein Profil gelöscht.'),
  ).toBeVisible();
  expect((await page.request.get(pathOf(newIcs))).status()).toBe(404);
  await expect
    .poll(() => hasSubscriber(email), { timeout: 90_000, intervals: [2_000] })
    .not.toBe(true);

  await page.goto(magic.path ?? '');
  await expect(page.getByText('Dieser Verwaltungslink ist ungültig.')).toBeVisible();
  const other = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  expect(await other.cookies()).toEqual([]);
  await other.close();
});

test('the same result page for a known and an unknown address', async ({ page }) => {
  const known = addressOf(stamp());
  const resultText = async (email: string): Promise<string> => {
    await fillQuestionnaire(page, { interests: ['Partys und Feiern'], mail: email });
    return page
      .locator('section')
      .filter({ has: page.getByRole('heading', { name: 'Dein Kalender ist fertig' }) })
      .innerText();
  };
  const unknown = await resultText(known);
  const repeated = await resultText(known);
  const fresh = await resultText(addressOf(stamp()));
  expect(repeated).toBe(unknown);
  expect(fresh).toBe(unknown);
});

test('an expired or invented link says one sentence and changes nothing', async ({ page }) => {
  await page.goto('/bestaetigen/' + 'x'.repeat(43));
  await expect(
    page.getByText('Dieser Link ist abgelaufen oder wurde schon benutzt.'),
  ).toBeVisible();
  await page.goto('/abo/' + 'x'.repeat(43));
  await expect(page.getByText('Dieser Verwaltungslink ist ungültig.')).toBeVisible();
  await expect(page.getByLabel('Mailadresse')).toBeVisible();
});

const PAGES = ['/start', '/abos', `/bestaetigen/${'x'.repeat(43)}`, `/abo/${'x'.repeat(43)}`];

for (const [name, viewport] of [
  ['phone', PHONE],
  ['desktop', DESKTOP],
] as const) {
  test(`axe in light and dark on the new pages (${name})`, async ({ page }) => {
    await page.setViewportSize(viewport);
    for (const path of PAGES) {
      await page.goto(path);
      await expect(page.locator('h1').first()).toBeVisible();
      await page.waitForLoadState('networkidle');
      await expectNoAxeViolations(page, `${path} ${name}`);
    }
  });
}

test('network allowlist over the new pages: own origin, no Set-Cookie, no cookie', async ({
  browser,
}) => {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE', viewport: PHONE });
  const page = await context.newPage();
  const foreign: string[] = [];
  const cookieHeaders: string[] = [];
  page.on('request', (r) => {
    const url = r.url();
    if (url.startsWith('data:') || url.startsWith('blob:')) return;
    if (new URL(url).origin !== new URL(BASE_URL).origin) foreign.push(url);
  });
  page.on('response', async (r) => {
    if ((await r.headerValue('set-cookie')) !== null) cookieHeaders.push(r.url());
  });
  await fillQuestionnaire(page, { interests: ['Partys und Feiern'] });
  for (const path of PAGES) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  }
  expect(foreign, 'requests to a foreign origin').toEqual([]);
  expect(cookieHeaders, 'responses with Set-Cookie').toEqual([]);
  expect(await context.cookies()).toEqual([]);
  await context.close();
});
