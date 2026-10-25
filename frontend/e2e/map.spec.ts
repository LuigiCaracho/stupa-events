/**
 * C acceptance in the browser (C contract 6.1): the world map and the campus map behind the production nginx with the
 * test tiles. WebGL needs the `map` project (`channel: 'chromium'`). The API answers come from route mocks
 * (`support/map-fixtures.ts`), so the cases are predictable. Covered: no request leaves the origin and no CSP
 * violation (T1, sprite and console T1b), clusters and the list twin (T3), the campus counts of building 9 (T4), "In meiner Nähe" without a
 * request that carries the position (T5), the position per SPA navigation under an active service worker (T6), axe in
 * both themes (T8) and the phone (T9). T2 (Range) is `deploy/tiles-smoke.sh`. T7 (pin sheet) is in `venue-pin.spec.ts`.
 */
import { type BrowserContext, type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';
import { NEAR_ME, PLACES, mockMapApi } from './support/map-fixtures';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://127.0.0.1:8081';
const DESKTOP = { width: 1280, height: 900 };
const PHONE = { width: 390, height: 844 };
const TOTAL = PLACES.reduce((sum, p) => sum + p.events, 0);

test.use({ baseURL: BASE_URL, locale: 'de-DE', viewport: DESKTOP });

const map = (page: Page) => page.locator('app-map');
const ready = (page: Page) =>
  expect(map(page)).toHaveAttribute('data-map-state', 'ready', { timeout: 30_000 });
const settle = (page: Page) => page.waitForTimeout(1_200);

async function watchViolations(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as { __csp: string[] }).__csp = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      (window as unknown as { __csp: string[] }).__csp.push(
        `${e.violatedDirective} ${e.blockedURI}`,
      ),
    );
  });
}

const violations = (page: Page): Promise<string[]> =>
  page.evaluate(() => (window as unknown as { __csp: string[] }).__csp);

async function openWorld(page: Page): Promise<void> {
  await mockMapApi(page);
  await page.goto('/karte');
  await ready(page);
}

test('T1: the map loads without a request to a third party and without a CSP violation', async ({
  page,
}) => {
  const origins = new Set<string>();
  const cookies: string[] = [];
  page.on('request', (r) => origins.add(new URL(r.url()).origin));
  page.on('response', async (r) => {
    if ((await r.headerValue('set-cookie')) !== null) cookies.push(r.url());
  });
  await watchViolations(page);
  await openWorld(page);
  await page.goto('/campus');
  await ready(page);
  await settle(page);
  expect([...origins]).toEqual([new URL(BASE_URL).origin]);
  expect(await violations(page)).toEqual([]);
  expect(cookies).toEqual([]);
  await expect(map(page)).toHaveAttribute('data-feature-count', '3');
});

test('T1b: the sprite is requested with an absolute URL, answers 200 and the console stays clean', async ({
  page,
}) => {
  const sprites: { url: string; status: number }[] = [];
  const errors: string[] = [];
  page.on('response', (r) => {
    if (r.url().includes('/sprites/')) sprites.push({ url: r.url(), status: r.status() });
  });
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await openWorld(page);
  await settle(page);
  expect(sprites.length).toBeGreaterThan(0);
  expect(sprites.every((s) => s.status === 200 && s.url.startsWith(BASE_URL))).toBe(true);
  expect(errors).toEqual([]);
});

test('T3: clusters, a click zooms, a cluster at one place filters the list', async ({ page }) => {
  await openWorld(page);
  await settle(page);
  await expect(map(page)).toHaveAttribute('data-feature-count', String(TOTAL));
  await expect
    .poll(async () => Number(await map(page).getAttribute('data-cluster-count')))
    .toBeGreaterThan(0);
  await expect(page.getByRole('link', { name: /Abend/ })).toHaveCount(TOTAL);

  const canvas = map(page).locator('canvas').first();
  const zoom = async () => Number(await map(page).getAttribute('data-zoom'));
  const before = await zoom();
  await canvas.click();
  await expect.poll(zoom).toBeGreaterThan(before + 0.5);
  await settle(page);
  await canvas.click();
  await expect(page.getByText('Nur Treffer an diesem Ort.')).toBeVisible();
  await expect(page.getByRole('link', { name: /Kinosaal 9-133 Abend/ })).toHaveCount(12);
  await expect(page.getByRole('link', { name: /Abend/ })).toHaveCount(12);
  await page.getByRole('button', { name: 'Alle zeigen' }).click();
  await expect(page.getByRole('link', { name: /Abend/ })).toHaveCount(TOTAL);
});

test('T4: building 9 counts three events on the map and in the table, and opens their list', async ({
  page,
}) => {
  await mockMapApi(page);
  await page.goto('/campus');
  await ready(page);
  await expect(map(page)).toHaveAttribute('data-feature-count', '3');
  const row = page.getByRole('row', { name: /Gebäude 9/ });
  await expect(row.getByRole('cell', { name: '3' })).toBeVisible();
  await row.getByRole('button', { name: 'Anzeigen' }).click();
  await expect(page.getByRole('heading', { name: 'Gebäude 9: 3 Events' })).toBeVisible();
  for (const title of ['Kino im Kinosaal', 'Maker Space Treff', 'FSI Frühstück']) {
    await expect(page.getByRole('link', { name: title })).toBeVisible();
  }
  await expect(page.getByText('Lage ungefähr').first()).toBeVisible();
});

async function allowLocation(context: BrowserContext): Promise<void> {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation(NEAR_ME);
}

test('T5: "In meiner Nähe" sorts the list in the browser and sends the position nowhere', async ({
  page,
  context,
}) => {
  await allowLocation(context);
  await openWorld(page);
  await settle(page);
  const sent: string[] = [];
  page.on('request', (r) => sent.push(`${r.url()} ${r.postData() ?? ''}`));
  await page.getByRole('button', { name: 'In meiner Nähe' }).click();
  await expect(page.getByRole('link', { name: /Aula Abend/ }).first()).toBeVisible();
  await expect(page.locator('.map__rows a').first()).toContainText('Aula');
  await expect(
    page
      .locator('.map__rows')
      .getByText(/\d+(,\d)? km|\d+ m$/)
      .first(),
  ).toBeVisible();
  await settle(page);
  expect(
    sent.filter((line) => /48\.48|9\.18|lat=|lon=|bbox|latitude|longitude/.test(line)),
  ).toEqual([]);
  expect(sent.filter((line) => /\/api\//.test(line))).toEqual([]);
});

test('T5: without permission the list says so and stays in date order', async ({ browser }) => {
  const context = await browser.newContext({ permissions: [], locale: 'de-DE', viewport: DESKTOP });
  const page = await context.newPage();
  await openWorld(page);
  await page.getByRole('button', { name: 'In meiner Nähe' }).click();
  await expect(page.getByText('Standort nicht verfügbar. Sortiert wird nach Datum.')).toBeVisible();
  await context.close();
});

test('T6: the position works after a navigation inside the app under an active service worker', async ({
  page,
  context,
}) => {
  test.setTimeout(120_000);
  await allowLocation(context);
  await mockMapApi(context);
  await page.goto('/');
  await page
    .waitForFunction(() => !!navigator.serviceWorker?.controller, undefined, { timeout: 60_000 })
    .catch(async () => {
      await page.reload();
      await page.waitForFunction(() => !!navigator.serviceWorker?.controller, undefined, {
        timeout: 60_000,
      });
    });
  await page
    .getByRole('navigation', { name: 'Hauptnavigation' })
    .getByRole('link', { name: 'Karte' })
    .click();
  await ready(page);
  await page.getByRole('button', { name: 'In meiner Nähe' }).click();
  await expect(page.locator('.map__rows a').first()).toContainText('Aula');
  await expect(page.getByText('Standort nicht verfügbar')).toHaveCount(0);
});

for (const [name, size] of [
  ['1280', DESKTOP],
  ['390', PHONE],
] as const) {
  test(`T8: axe on the world and the campus map at ${name} px`, async ({ page }) => {
    await page.setViewportSize(size);
    await openWorld(page);
    await settle(page);
    await expectNoAxeViolations(page, `/karte ${name}`);
    await page.goto('/campus');
    await ready(page);
    await settle(page);
    await expectNoAxeViolations(page, `/campus ${name}`);
  });
}

test('T9: on the phone nothing scrolls sideways, the bar leads to Karte and the list follows the map', async ({
  page,
}) => {
  await page.setViewportSize(PHONE);
  await openWorld(page);
  await settle(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  const bar = page.getByRole('navigation', { name: 'Hauptnavigation' }).last();
  await expect(bar.getByRole('link')).toHaveText(['Heute', 'Kalender', 'Karte', 'Abos']);
  await expect(bar.getByRole('link', { name: 'Karte' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Treffer' })).toBeVisible();
});
