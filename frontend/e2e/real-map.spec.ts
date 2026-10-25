/**
 * C acceptance on real data (C contract 6.5): the maps against the host API and the built tiles, without route mocks.
 * Needs the data of `python -m scripts.c_acceptance setup` (hand pins for Davos, Ischgl, Europapark and Straßburg,
 * three events today in building 9) and a production nginx with the tiles volume; runs only with `E2E_REAL_MAP=1`.
 * Covered: only the own origin, Range answers for the archives, no CSP violation and no cookie; the four destinations
 * on the world map with clusters and the same hits in the list; "In meiner Nähe" without a request that carries the
 * position; building 9 counts three events; axe in both themes on the phone.
 */
import { type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://127.0.0.1:8081';
const DESTINATIONS = ['Davos', 'Ischgl', 'Europapark', 'Straßburg'];
const BUILDING_9 = ['kinosaal-9-133', 'maker-space-9-229', 'fsi-9-u09'];

test.skip(!process.env['E2E_REAL_MAP'], 'needs the data of scripts.c_acceptance setup');
test.use({ baseURL: BASE_URL, locale: 'de-DE', viewport: { width: 1280, height: 900 } });

const map = (page: Page) => page.locator('app-map');
const ready = (page: Page) =>
  expect(map(page)).toHaveAttribute('data-map-state', 'ready', { timeout: 30_000 });
const settle = (page: Page) => page.waitForTimeout(1_500);

test('the maps load from the own origin only, the archives answer with 206', async ({ page }) => {
  const origins = new Set<string>();
  const ranges: number[] = [];
  const cookies: string[] = [];
  page.on('request', (r) => origins.add(new URL(r.url()).origin));
  page.on('response', async (r) => {
    if (r.url().includes('/tiles/')) ranges.push(r.status());
    if ((await r.headerValue('set-cookie')) !== null) cookies.push(r.url());
  });
  await page.addInitScript(() => {
    (window as unknown as { __csp: string[] }).__csp = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      (window as unknown as { __csp: string[] }).__csp.push(
        `${e.violatedDirective} ${e.blockedURI}`,
      ),
    );
  });
  await page.goto('/karte');
  await ready(page);
  await settle(page);
  await page.goto('/campus');
  await ready(page);
  await settle(page);
  expect([...origins]).toEqual([new URL(BASE_URL).origin]);
  expect(ranges.length).toBeGreaterThan(0);
  expect(ranges.every((s) => s === 206)).toBe(true);
  expect(cookies).toEqual([]);
  expect(await page.evaluate(() => (window as unknown as { __csp: string[] }).__csp)).toEqual([]);
});

test('the world map shows the four destinations in clusters, the list has the same hits', async ({
  page,
}) => {
  await page.goto('/karte');
  await ready(page);
  await settle(page);
  const features = Number(await map(page).getAttribute('data-feature-count'));
  expect(features).toBeGreaterThanOrEqual(DESTINATIONS.length);
  await expect
    .poll(async () => Number(await map(page).getAttribute('data-cluster-count')))
    .toBeGreaterThan(0);
  const rows = page.locator('.map__rows a');
  await expect(rows).toHaveCount(features);
  for (const name of DESTINATIONS) {
    await expect(page.locator('.map__rows li').filter({ hasText: name }).first()).toBeVisible();
  }
  await page.screenshot({ path: 'test-results/real-map-world.png' });
});

test('"In meiner Nähe" sorts by distance and sends the position nowhere', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 48.4829, longitude: 9.1873 });
  await page.goto('/karte');
  await ready(page);
  await settle(page);
  const sent: string[] = [];
  page.on('request', (r) => sent.push(`${r.url()} ${r.postData() ?? ''}`));
  await page.getByRole('button', { name: 'In meiner Nähe' }).click();
  const rows = page.locator('.map__rows li');
  await expect(rows.first()).toContainText(/9-133|9-229|9-U09/);
  await expect(rows.first()).toContainText(/\d+ m|\d+(,\d)? km/);
  await expect(rows.last()).not.toContainText(/9-133|9-229|9-U09/);
  await settle(page);
  expect(
    sent.filter((line) => /48\.48|9\.18|lat=|lon=|bbox|latitude|longitude/.test(line)),
  ).toEqual([]);
  expect(sent.filter((line) => /\/api\//.test(line))).toEqual([]);
});

test('building 9 counts the three events in the table and lists them', async ({ page }) => {
  await page.goto('/campus');
  await ready(page);
  const row = page.getByRole('row', { name: /Gebäude 9/ });
  await expect(row.getByRole('cell', { name: '3', exact: true })).toBeVisible();
  await row.getByRole('button', { name: 'Anzeigen' }).click();
  await expect(page.getByRole('heading', { name: 'Gebäude 9: 3 Events' })).toBeVisible();
  for (const slug of BUILDING_9) {
    await expect(page.getByRole('link', { name: new RegExp(`C Campus ${slug}`) })).toBeVisible();
  }
  await page.screenshot({ path: 'test-results/real-map-campus.png', fullPage: true });
});

test('axe finds nothing serious on both maps on the phone, light and dark', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/karte', '/campus']) {
    await page.goto(path);
    await ready(page);
    await settle(page);
    await expectNoAxeViolations(page, `${path} 390 real`);
  }
});
