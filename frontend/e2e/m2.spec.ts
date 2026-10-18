/**
 * M2 acceptance (PLAN 16.1, row M2) against the compose stack with the Keycloak dev IdP: the editor
 * sees the admin area without the mapping tab and adds a category; the admin adds and removes a group
 * mapping and sees `reserved_group_prefix` for a reserved group; organizer-fsi gets a not-found answer
 * for a dossier of another organization; revoking the other sessions ends the session of the second
 * browser but not the one that revokes.
 */
import { type Browser, type Page, expect, test } from '@playwright/test';
import { createDossier } from './support/dossier';
import { login } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const SLUG = `e2e-${STAMP}`;
const CATEGORY = `E2E Kategorie ${STAMP}`;
const GROUP = `events-e2e-${STAMP}`;

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

async function fresh(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  return context.newPage();
}

test('editor: Verwaltung shows the taxonomy tabs and creates a category', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'editor');
  await page.getByRole('link', { name: 'Verwaltung' }).first().click();
  await page.waitForURL(/\/verwaltung\/kategorien$/);
  await expect(page.getByRole('tab')).toHaveText(['Kategorien', 'Orte', 'Organisationen']);

  await page.getByRole('button', { name: 'Hinzufügen' }).click();
  await page.getByRole('textbox', { name: 'Name' }).fill(CATEGORY);
  await page.getByRole('textbox', { name: 'Slug' }).fill(SLUG);
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();
  await expect(page.getByRole('cell', { name: CATEGORY })).toBeVisible();

  const categories = await (await page.request.get('/api/categories')).json();
  expect(categories.map((c: { slug: string }) => c.slug)).toContain(SLUG);

  await page.getByRole('button', { name: 'Hinzufügen' }).click();
  await page.getByRole('textbox', { name: 'Name' }).fill('Doppelt');
  await page.getByRole('textbox', { name: 'Slug' }).fill(SLUG);
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Slug schon vergeben.')).toBeVisible();
  await page.context().close();
});

test('editor: the mapping tab is not reachable', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'editor');
  await page.goto('/verwaltung/zuordnungen');
  await page.waitForURL(/\/forbidden$/);
  const response = await page.request.get('/api/admin/group-mappings');
  expect(response.status()).toBe(403);
  await page.context().close();
});

test('admin: adds a group mapping and removes it again', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'admin');
  await page.goto('/verwaltung/zuordnungen');
  await page.getByRole('button', { name: 'Zuordnung hinzufügen' }).click();
  await page.getByRole('textbox', { name: /Gruppe/ }).fill(GROUP);
  await page.getByRole('combobox', { name: /Rolle/ }).click();
  await page.getByRole('option', { name: 'Lesend' }).click();
  await page.getByRole('combobox', { name: 'Organisation' }).click();
  await page.getByRole('option', { name: 'Fachschaft Informatik' }).click();
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Gespeichert.')).toBeVisible();

  const row = page.getByRole('row', { name: new RegExp(GROUP) });
  await expect(row).toBeVisible();
  await row.getByRole('button', { name: 'Löschen' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Löschen' }).click();
  await expect(row).toBeHidden();

  await page.getByRole('button', { name: 'Zuordnung hinzufügen' }).click();
  await page.getByRole('textbox', { name: /Gruppe/ }).fill(`events-system:${STAMP}`);
  await page.getByRole('combobox', { name: /Rolle/ }).click();
  await page.getByRole('option', { name: 'Redaktion' }).click();
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Gruppe beginnt mit reserviertem Präfix events-system:.')).toBeVisible();
  await page.context().close();
});

test('organizer-fsi: a dossier of another organization answers not found', async ({ browser }) => {
  const makers = await fresh(browser);
  await login(makers, 'organizer-makers');
  const foreignId = await createDossier(makers, `E2E fremd ${STAMP}`);
  await makers.context().close();

  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  expect((await page.request.get(`/api/events/${foreignId}`)).status()).toBe(404);
  await page.goto(`/dossiers/${foreignId}`);
  await expect(page.getByRole('alert')).toContainText('Diese Seite gibt es nicht oder du hast keinen Zugriff.');
  await page.context().close();
});

test('Sitzungen widerrufen: the other session needs a new login, this one stays', async ({ browser }) => {
  const here = await fresh(browser);
  const other = await fresh(browser);
  await login(here, 'organizer-fsi');
  await login(other, 'organizer-fsi');
  expect((await other.request.get('/api/auth/me')).status()).toBe(200);

  await here.goto('/konto');
  await here.getByRole('button', { name: 'Andere Sitzungen widerrufen' }).click();
  await here.getByRole('dialog').getByRole('button', { name: 'Andere Sitzungen widerrufen' }).click();
  await expect(here.getByText(/Sitzungen? beendet\./)).toBeVisible();

  expect((await other.request.get('/api/auth/me')).status()).toBe(401);
  expect((await here.request.get('/api/auth/me')).status()).toBe(200);
  await here.context().close();
  await other.context().close();
});
