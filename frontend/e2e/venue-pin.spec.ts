/**
 * C2 acceptance in the browser (C contract 6.1, T7 and the Orte part of T8): the pin sheet of the venue table. A click on
 * the map fills latitude and longitude, "Adresse suchen" proposes a position (the server answer is a route mock) and
 * is taken over as `nominatim`, a private venue cannot be searched and causes no request. The sign-in and the admin API are
 * mocks, so the spec needs no Keycloak; the tiles are the test tiles of the web stack.
 */
import { type Page, expect, test } from '@playwright/test';
import { expectNoAxeViolations } from './support/axe';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://127.0.0.1:8081';
test.use({ baseURL: BASE_URL, locale: 'de-DE', viewport: { width: 1280, height: 900 } });

const venue = (over: object) => ({
  id: 'ven-1',
  slug: 'foyer',
  name: 'Foyer',
  address: 'Alteburgstraße 150',
  postcode: '72762',
  city: 'Reutlingen',
  buildingNo: null,
  roomKey: null,
  campusBuildingNo: null,
  lat: null,
  lon: null,
  publicPrecision: 'building',
  isPrivate: false,
  geocodeSource: null,
  geocodedAt: null,
  legacyWpId: null,
  notes: null,
  active: true,
  createdAt: '2026-10-01T00:00:00Z',
  updatedAt: '2026-10-01T00:00:00Z',
  ...over,
});

const PRINCIPAL = {
  sub: 'e2e',
  email: 'admin@example.org',
  displayName: 'Admin',
  roles: ['admin'],
  permissions: ['venue.manage'],
  groups: [],
  organizations: [],
};

interface Calls {
  patches: Record<string, unknown>[];
  geocodes: number;
}

async function mockAdmin(page: Page): Promise<Calls> {
  const calls: Calls = { patches: [], geocodes: 0 };
  await page.route('**/api/auth/me', (r) => r.fulfill({ json: PRINCIPAL }));
  await page.route('**/api/admin/venues', (r) =>
    r.fulfill({
      json: [venue({}), venue({ id: 'ven-2', slug: 'privat', name: 'Privat', isPrivate: true })],
    }),
  );
  await page.route('**/api/admin/venues/*', (r) => {
    calls.patches.push(r.request().postDataJSON() as Record<string, unknown>);
    return r.fulfill({ json: venue({}) });
  });
  await page.route('**/api/admin/venues/*/geocode', (r) => {
    calls.geocodes += 1;
    return r.fulfill({
      json: {
        found: true,
        lat: '48.482617',
        lon: '9.187312',
        displayName: 'Alteburgstraße 150',
        cached: false,
        attribution: '© OpenStreetMap',
      },
    });
  });
  return calls;
}

async function openSheet(page: Page, name: string): Promise<void> {
  await page.goto('/verwaltung/orte');
  await page.getByRole('cell', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Pin setzen' }).click();
  await expect(page.getByRole('dialog', { name: 'Pin setzen' })).toBeVisible();
  await expect(page.locator('app-map')).toHaveAttribute('data-map-state', 'ready', {
    timeout: 30_000,
  });
}

test('a click on the map sets the pin and the number fields', async ({ page }) => {
  const calls = await mockAdmin(page);
  await openSheet(page, 'Foyer');
  await expectNoAxeViolations(page, 'pin sheet', '[role="dialog"]');
  const dialog = page.getByRole('dialog', { name: 'Pin setzen' });
  await expect(dialog.getByRole('button', { name: 'Übernehmen' })).toBeDisabled();
  await page
    .locator('app-map canvas')
    .first()
    .click({ position: { x: 200, y: 150 } });
  await dialog.getByRole('button', { name: 'Übernehmen' }).click();
  await expect(dialog).toBeHidden();
  const lat = Number(await page.getByRole('spinbutton', { name: 'Breite' }).inputValue());
  const lon = Number(await page.getByRole('spinbutton', { name: 'Länge' }).inputValue());
  expect(lat).toBeGreaterThan(40);
  expect(lon).toBeGreaterThan(5);
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect.poll(() => calls.patches.length).toBe(1);
  expect(calls.patches[0]).toMatchObject({ lat: expect.any(Number), lon: expect.any(Number) });
  expect(calls.patches[0]).not.toHaveProperty('geocodeSource');
});

test('"Adresse suchen" proposes a position that is saved as a search result', async ({ page }) => {
  const calls = await mockAdmin(page);
  await openSheet(page, 'Foyer');
  const dialog = page.getByRole('dialog', { name: 'Pin setzen' });
  await dialog.getByRole('button', { name: 'Adresse suchen' }).click();
  await expect(dialog.getByText(/Vorschlag von OpenStreetMap\. Prüfe den Pin\./)).toBeVisible();
  await dialog.getByRole('button', { name: 'Übernehmen' }).click();
  await expect(page.getByRole('spinbutton', { name: 'Breite' })).toHaveValue('48.482617');
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect.poll(() => calls.patches.length).toBe(1);
  expect(calls.patches[0]).toMatchObject({
    lat: 48.482617,
    lon: 9.187312,
    geocodeSource: 'nominatim',
  });
  expect(calls.geocodes).toBe(1);
});

test('a private venue cannot be searched and causes no request', async ({ page }) => {
  const calls = await mockAdmin(page);
  await openSheet(page, 'Privat');
  const dialog = page.getByRole('dialog', { name: 'Pin setzen' });
  await expect(dialog.getByRole('button', { name: 'Adresse suchen' })).toBeDisabled();
  await expect(dialog.getByText('Private Orte werden nicht extern gesucht.')).toBeVisible();
  await dialog
    .getByRole('button', { name: 'Adresse suchen' })
    .click({ force: true })
    .catch(() => undefined);
  expect(calls.geocodes).toBe(0);
});
