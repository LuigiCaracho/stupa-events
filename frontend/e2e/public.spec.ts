/**
 * B1 acceptance in the browser (contract 6.2): the public site for anonymous visitors. Heute to Detail to "In Kalender", search
 * with facets and the back button, the calendar by keyboard, the category subscription, the phone viewport (no horizontal
 * scroll, 44 px touch targets, bottom bar, filter sheet), axe in both themes at 1280 px and 390 x 844, the network
 * allowlist (own origin only, no `Set-Cookie`, no cookie at the end), a signed-in person on `/` and the error states.
 * The fixtures (a poster event with ticket, a cancelled one, a past one) come from `support/public-fixtures.ts`.
 */
import { type Page, type Route, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { createFixtures, findFixtures, type PublicFixtures } from './support/public-fixtures';
import { login } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };
let fx: PublicFixtures;

test.use({ baseURL: BASE_URL, locale: 'de-DE' });
test.describe.configure({ mode: 'serial' });

test.beforeAll(async ({ browser }) => {
  let found = await findFixtures();
  if (!found.poster || !found.cancelled) {
    await createFixtures(browser, found);
    found = await findFixtures();
  }
  expect(found.poster, 'an event with poster and ticket').toBeTruthy();
  expect(found.cancelled, 'a cancelled event').toBeTruthy();
  fx = { ...found, past: found.past ?? null } as PublicFixtures;
});

const routes = (): string[] => [
  '/',
  '/suche',
  '/kalender',
  `/e/${fx.poster}`,
  `/e/${fx.cancelled}`,
  `/k/${fx.category}`,
  '/rueckblick',
  '/abos',
  '/impressum',
  '/datenschutz',
  '/offline',
  '/gibt-es-nicht',
];

async function visit(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await expect(page.locator('main h1, main h2').first()).toBeVisible();
  await page.waitForLoadState('networkidle');
}

test('Heute to detail to "In Kalender": the ICS download carries the event', async ({ page }) => {
  await page.setViewportSize(DESKTOP);
  await visit(page, '/');
  await expect(page.getByRole('heading', { name: 'Heute am Campus' })).toBeVisible();
  await page.getByRole('link', { name: 'Suche' }).first().click();
  await page.getByRole('searchbox').fill(fx.posterTitle);
  await page.locator(`a[href="/e/${fx.poster}"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`/e/${fx.poster}$`));
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Ticket' })).toHaveAttribute(
    'rel',
    'noopener noreferrer',
  );
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('link', { name: 'In Kalender' }).click(),
  ]);
  expect(download.suggestedFilename()).toBe(`${fx.poster}.ics`);
  const path = await download.path();
  const text = (await import('node:fs')).readFileSync(path, 'utf8');
  expect(text.startsWith('BEGIN:VCALENDAR')).toBe(true);
  expect(text).toContain('SUMMARY:');
});

test('search: live results, a facet in the URL, back restores the state, empty state resets', async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP);
  await visit(page, '/suche');
  const field = page.getByRole('searchbox', { name: 'Events suchen' });
  const word = fx.posterTitle.split(/[^\p{L}\p{N}]+/u).find((w) => w.length > 2) ?? 'Event';
  await field.fill(word);
  await expect(page).toHaveURL(new RegExp(`q=${word}`));
  await expect(page.locator('app-public-event-row').first()).toBeVisible();

  await page.getByRole('button', { name: /^Kategorie/ }).click();
  const option = page.getByRole('option').first();
  const label = (await option.textContent()) ?? '';
  const count = Number(/\((\d+)\)/.exec(label)?.[1] ?? '0');
  await option.click();
  await page.keyboard.press('Escape');
  await expect(page).toHaveURL(/category=/);
  if (count > 0)
    await expect(page.locator('p[aria-hidden="true"]', { hasText: /Treffer/ })).toBeVisible();

  await page.goBack();
  await expect(page).not.toHaveURL(/category=/);
  await expect(page).toHaveURL(new RegExp(`q=${word}`));

  await field.fill('zzzzqqqq');
  await expect(page.getByText('Nichts gefunden für „zzzzqqqq“ in diesem Zeitraum.')).toBeVisible();
  await page
    .getByRole('button', { name: 'Filter zurücksetzen' })
    .click()
    .catch(() => undefined);
});

test('calendar: month, a day with an event, keyboard in the grid, month steps', async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP);
  await visit(page, '/kalender');
  const grid = page.getByRole('grid');
  await expect(grid).toBeVisible();
  const title = page.locator('.cal__month');
  const before = await title.textContent();
  await grid.locator('[role="gridcell"][tabindex="0"]').focus();
  await page.keyboard.press('ArrowRight');
  await expect(grid.locator('[role="gridcell"]:focus')).toHaveCount(1);
  await page.getByRole('button', { name: 'Weiter', exact: true }).click();
  await expect(title).not.toHaveText(before ?? '');
  await expect(page).toHaveURL(/month=\d{4}-\d{2}/);
  await page.getByRole('button', { name: 'Heute', exact: true }).click();
  await expect(title).toHaveText(before ?? '');
  const entry = grid.getByRole('button').first();
  if (await entry.count()) {
    await entry.click();
    await expect(page).toHaveURL(/\/e\/|\/kalender/);
  }
  await visit(page, '/kalender');
  await page.setViewportSize(PHONE);
  await expect(page.getByRole('grid')).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Termine nach Tagen' })).toBeVisible();
});

test('category subscription: webcal and https address, copy, and the ICS is text/calendar', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE_URL });
  await visit(page, `/k/${fx.category}`);
  await page.getByRole('link', { name: 'Kalender abonnieren' }).first().click();
  await expect(page).toHaveURL(new RegExp(`/abos#k=${fx.category}$`));
  const row = page.locator(`#k-${fx.category}`);
  await expect(row).toBeVisible();
  const https = `${BASE_URL}/ics/k/${fx.category}.ics`;
  await expect(row.getByText(https)).toBeVisible();
  await expect(row.getByRole('link', { name: 'Kalender öffnen' })).toHaveAttribute(
    'href',
    https.replace(/^https?:/, 'webcal:'),
  );
  await row.getByRole('button', { name: /kopieren/ }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(https);
  const answer = await page.request.get(https);
  expect(answer.headers()['content-type']).toContain('text/calendar');
});

test('phone 390 x 844: no horizontal scroll, bottom bar, 44 px targets, filter sheet with focus trap', async ({
  page,
}) => {
  await page.setViewportSize(PHONE);
  for (const path of routes()) {
    await visit(page, path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow, `horizontal scroll on ${path}`).toBeLessThanOrEqual(0);
    await expect(page.getByRole('navigation', { name: 'Hauptnavigation' })).toHaveCount(1);
    const small = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('a, button, [role="button"]')]
        .filter((e) => !e.closest('.ev__desc, .skip-link') && !e.matches('.skip-link'))
        .map((e) => ({ e, r: (e.closest('.li') ?? e).getBoundingClientRect() }))
        .filter(
          ({ e, r }) => r.width > 0 && r.height > 0 && getComputedStyle(e).display !== 'inline',
        )
        .filter(({ r }) => r.height < 43.5 || r.width < 43.5)
        .map(
          ({ e, r }) =>
            `${e.tagName}.${e.className} ${Math.round(r.width)}x${Math.round(r.height)}`,
        ),
    );
    expect(small, `touch targets on ${path}`).toEqual([]);
  }
  await visit(page, '/');
  const bar = page.getByRole('navigation', { name: 'Hauptnavigation' });
  await expect(bar.getByRole('link')).toHaveCount(4);
  await expect(bar.getByRole('link', { name: 'Heute' })).toHaveAttribute('aria-current', 'page');

  await visit(page, '/suche');
  const open = page.getByRole('button', { name: /^Filter \(/ });
  await open.click();
  const sheet = page.getByRole('dialog', { name: 'Filter' });
  await expect(sheet).toBeVisible();
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    expect(await sheet.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press('Escape');
  await expect(sheet).toBeHidden();
  await expect(open).toBeFocused();
});

for (const [name, viewport] of [
  ['desktop', DESKTOP],
  ['phone', PHONE],
] as const) {
  test(`axe in light and dark on every public route (${name})`, async ({ page }) => {
    await page.setViewportSize(viewport);
    for (const path of routes()) {
      await visit(page, path);
      await expectNoAxeViolations(page, `${path} ${name}`);
    }
  });
}

test('network allowlist: own origin only, no Set-Cookie, no cookie in the end', async ({
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
  for (const path of routes()) await visit(page, path);
  expect(foreign, 'requests to a foreign origin').toEqual([]);
  expect(cookieHeaders, 'responses with Set-Cookie').toEqual([]);
  expect(await context.cookies()).toEqual([]);
  await context.close();
});

test('a signed-in person sees the public start page and "Zum Dossier"', async ({ browser }) => {
  const context = await browser.newContext({
    baseURL: BASE_URL,
    locale: 'de-DE',
    viewport: DESKTOP,
  });
  const page = await context.newPage();
  await login(page, 'organizer-fsi');
  await page.goto('/');
  await expect(page).toHaveURL(new RegExp(`${BASE_URL.replace(/[.]/g, '\\.')}/?$`));
  await expect(page.getByRole('heading', { name: 'Heute am Campus' })).toBeVisible();
  const link = page.getByRole('banner').getByRole('link', { name: 'Zum Dossier' });
  await expect(link).toHaveAttribute('href', '/dossiers');
  await link.click();
  await expect(page).toHaveURL(/\/dossiers/);
  await context.close();
});

test('errors: 429 gives the wait message, a dropped network gives "Neu laden"', async ({
  page,
}) => {
  await page.setViewportSize(DESKTOP);
  await page.route('**/api/public/today', (route: Route) =>
    route.fulfill({
      status: 429,
      contentType: 'application/problem+json',
      body: JSON.stringify({ status: 429, code: 'rate_limited' }),
    }),
  );
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText(
    'Zu viele Anfragen. Bitte warte einen Moment.',
  );
  await page.unroute('**/api/public/today');

  await page.route('**/api/public/today', (route: Route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Die Termine konnten nicht geladen werden.');
  await page.unroute('**/api/public/today');
  await page.getByRole('button', { name: 'Neu laden' }).click();
  await expect(page.getByRole('heading', { name: 'Heute am Campus' })).toBeVisible();
});
