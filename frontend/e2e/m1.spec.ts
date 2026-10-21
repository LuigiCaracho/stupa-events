/**
 * M1 acceptance (PLAN 16.1), cut down by M5b, against the compose stack with the Keycloak dev IdP: organizer-fsi signs in (the
 * role comes from the group), creates a dossier, drops a poster and publishes it; the event is in the public feed with its
 * image. A viewer of the organization cannot publish (403, no button); an editor can publish a draft of an organization.
 */
import { type APIRequestContext, type Browser, type Page, expect, request, test } from '@playwright/test';
import { createDossier, runAction, uploadPoster } from './support/dossier';
import { login, logout, postJson, waitForCleanPoster } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const TITLE = `E2E Movienight ${STAMP}`;
const TITLE_BY_EDITOR = `E2E Redaktion ${STAMP}`;
const ALT = 'Plakat der Movienight mit Filmrolle';
const CREDIT = 'Fachschaft Informatik';

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

let dossierId = '';
let draftId = '';

async function fresh(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  return context.newPage();
}

test('organizer-fsi: login shows the role from the group, a poster and publishing', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  const me = await (await page.request.get('/api/auth/me')).json();
  expect(me.organizations).toEqual(
    expect.arrayContaining([expect.objectContaining({ slug: 'fsi', role: 'organizer' })]),
  );
  await expect(page.getByRole('heading', { level: 1, name: 'Events' })).toBeVisible();

  dossierId = await createDossier(page, TITLE);
  await expect(page.locator('app-status-text', { hasText: 'Entwurf' }).first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Bild' })).toBeVisible();
  await uploadPoster(page, { altText: ALT, credit: CREDIT });
  await expect(page.getByText(ALT, { exact: true })).toBeVisible();
  await waitForCleanPoster(page, dossierId);

  await page.reload();
  await runAction(page, 'Veröffentlichen', 'Veröffentlicht');

  draftId = await createDossier(page, TITLE_BY_EDITOR);
  await logout(page);
  await page.context().close();
});

test('the event is in the public feed with its image and without cookies', async () => {
  const anonymous: APIRequestContext = await request.newContext({ baseURL: BASE_URL });
  const feed = await anonymous.get('/api/public/feed/events?limit=500');
  expect(feed.status()).toBe(200);
  expect(feed.headers()['set-cookie']).toBeUndefined();
  const body = await feed.json();
  const item = body.items.find((i: { id: string }) => i.id === dossierId);
  expect(item).toBeTruthy();
  expect(item.title).toBe(TITLE);
  expect(item.image).toMatchObject({ alt: ALT, credit: CREDIT });
  expect(body.items.find((i: { id: string }) => i.id === draftId)).toBeUndefined();

  const media = await anonymous.get(new URL(item.image.url).pathname);
  expect(media.status()).toBe(200);
  expect(media.headers()['content-type']).toBe('image/webp');
  await anonymous.dispose();
});

test('a viewer of the organization cannot publish: no button, 403 from the API', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'viewer-fsi');
  await page.goto(`/dossiers/${draftId}`);
  await expect(page.getByRole('heading', { level: 1, name: TITLE_BY_EDITOR })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Veröffentlichen' })).toHaveCount(0);
  const response = await postJson(page, `/api/events/${draftId}/publish`);
  expect(response.status()).toBe(403);
  await page.context().close();
});

test('editor: publishes a draft of an organization without a poster', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'editor');
  await page.goto(`/dossiers/${draftId}`);
  await runAction(page, 'Veröffentlichen', 'Veröffentlicht');
  const anonymous: APIRequestContext = await request.newContext({ baseURL: BASE_URL });
  const body = await (await anonymous.get('/api/public/feed/events?limit=500')).json();
  const item = body.items.find((i: { id: string }) => i.id === draftId);
  expect(item?.image).toBeNull();
  await anonymous.dispose();
  await page.context().close();
});
