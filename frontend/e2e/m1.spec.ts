/**
 * M1 acceptance (PLAN 16.1) against the compose stack with the Keycloak dev IdP: organizer-fsi creates
 * a dossier, uploads a poster and asks for approval; editor approves and publishes; the event is in
 * the public feed. Without a poster the approval is refused with 422 image_required.
 */
import {
  type APIRequestContext,
  type Browser,
  type Page,
  expect,
  request,
  test,
} from '@playwright/test';
import { confirmTransition, createDossier, setSummary, uploadPoster } from './support/dossier';
import { login, logout, postJson } from './support/session';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://localhost:8081';
const STAMP = Date.now();
const TITLE = `E2E Movienight ${STAMP}`;
const TITLE_NO_POSTER = `E2E ohne Poster ${STAMP}`;
const ALT = 'Plakat der Movienight mit Filmrolle';
const CREDIT = 'Fachschaft Informatik';

test.use({ baseURL: BASE_URL });
test.describe.configure({ mode: 'serial' });

let dossierId = '';
let noPosterId = '';

async function fresh(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ baseURL: BASE_URL, locale: 'de-DE' });
  return context.newPage();
}

async function planAndRequestApproval(page: Page, id: string, withSummary: string): Promise<void> {
  await page.goto(`/dossiers/${id}`);
  await confirmTransition(page, 'Planung starten', 'Planung');
  await setSummary(page, withSummary);
}

test('organizer-fsi: login shows the role from the group', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  const me = await (await page.request.get('/api/auth/me')).json();
  expect(me.organizations).toEqual(
    expect.arrayContaining([expect.objectContaining({ slug: 'fsi', role: 'organizer' })]),
  );
  await expect(page.getByRole('heading', { level: 1, name: 'Meine Aufgaben' })).toBeVisible();

  dossierId = await createDossier(page, TITLE);
  await expect(page.locator('app-status-text', { hasText: 'Idee' }).first()).toBeVisible();
  await planAndRequestApproval(page, dossierId, 'Film, Popcorn und Diskussion');

  await expect(page.getByRole('region', { name: 'Poster' })).toBeVisible();
  await uploadPoster(page, ALT, CREDIT);
  await expect(page.getByText(ALT, { exact: true })).toBeVisible();
  await expect
    .poll(
      async () => {
        const event = await (await page.request.get(`/api/events/${dossierId}`)).json();
        return event.poster?.scanStatus === 'clean' && event.poster?.derivatives !== null;
      },
      { timeout: 120_000, intervals: [2_000] },
    )
    .toBe(true);

  await page.reload();
  await confirmTransition(page, 'Freigabe anfragen', 'Freigabe');
  await expect(page.getByText(/In der Freigabe gesperrt/)).toBeVisible();

  noPosterId = await createDossier(page, TITLE_NO_POSTER);
  await planAndRequestApproval(page, noPosterId, 'Ohne Plakat eingereicht');
  await confirmTransition(page, 'Freigabe anfragen', 'Freigabe');

  await logout(page);
  await page.context().close();
});

test('organizer-fsi cannot approve its own dossier', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'organizer-fsi');
  const response = await postJson(page, `/api/events/${dossierId}/transitions/T04`);
  expect([403, 409, 422]).toContain(response.status());
  await page.context().close();
});

test('editor: approval without poster is refused with image_required', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'editor');
  await page.goto(`/dossiers/${noPosterId}`);
  await expect(page.getByRole('button', { name: 'Freigeben' })).toBeVisible();
  await expect(page.getByText('Poster fehlt oder ist nicht freigegeben.')).toBeVisible();

  await page.getByRole('button', { name: 'Freigeben' }).click();
  const dialog = page.getByRole('dialog', { name: 'Freigeben' });
  await expect(dialog.getByText('Poster fehlt oder ist nicht freigegeben.')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Schließen' }).click();

  const response = await postJson(page, `/api/events/${noPosterId}/transitions/T04`);
  expect(response.status()).toBe(422);
  const problem = await response.json();
  expect(problem.code).toBe('image_required');
  expect(problem.reasons[0].fixAction).toBe('upload_poster');
  await page.context().close();
});

test('editor: approves and publishes, the event appears in the feed', async ({ browser }) => {
  const page = await fresh(browser);
  await login(page, 'editor');
  await expect(page.getByRole('heading', { level: 1, name: 'Meine Aufgaben' })).toBeVisible();
  // The task list shows its first 50 entries and the dev DB holds many dossiers in review.
  await page.goto(`/pipeline?q=${encodeURIComponent(TITLE)}`);
  await page
    .getByRole('button', { name: new RegExp(TITLE) })
    .first()
    .click();
  await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible();
  await expect(page.getByText('Alles bereit.')).toBeVisible();

  await confirmTransition(page, 'Freigeben', 'Freigegeben');
  await confirmTransition(page, 'Veröffentlichen', 'Veröffentlicht');

  const anonymous: APIRequestContext = await request.newContext({ baseURL: BASE_URL });
  const feed = await anonymous.get('/api/public/feed/events');
  expect(feed.status()).toBe(200);
  expect(feed.headers()['set-cookie']).toBeUndefined();
  const body = await feed.json();
  const item = body.items.find((i: { id: string }) => i.id === dossierId);
  expect(item).toBeTruthy();
  expect(item.title).toBe(TITLE);
  expect(item.image).toMatchObject({ alt: ALT, credit: CREDIT });
  expect(body.items.find((i: { id: string }) => i.id === noPosterId)).toBeUndefined();

  const media = await anonymous.get(new URL(item.image.url).pathname);
  expect(media.status()).toBe(200);
  expect(media.headers()['content-type']).toBe('image/webp');
  await anonymous.dispose();
  await page.context().close();
});
