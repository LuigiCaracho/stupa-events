/** E2E helpers: Keycloak login and logout through the UI, and CSRF-aware API calls of a signed-in page. */
import { type APIResponse, type Page, expect } from '@playwright/test';

export const PASSWORD = 'password';

export async function login(page: Page, username: string): Promise<void> {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Mit Hochschul-Login anmelden' }).click();
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(PASSWORD);
  await page.locator('#kc-login').click();
  await page.waitForURL(/\/aufgaben/);
}

export async function logout(page: Page): Promise<void> {
  await page.goto('/konto');
  await page.getByRole('button', { name: 'Abmelden' }).click();
  const confirm = page.locator('#kc-logout');
  await confirm.waitFor({ state: 'visible', timeout: 5_000 }).then(
    () => confirm.click(),
    () => undefined,
  );
  await expect.poll(async () => (await page.request.get('/api/auth/me')).status()).toBe(401);
}

export async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const token = cookies.find((c) => c.name === 'XSRF-TOKEN')?.value;
  return token ? { 'X-XSRF-TOKEN': token } : {};
}

async function currentEtag(page: Page, path: string): Promise<Record<string, string>> {
  const id = /^\/api\/events\/([^/]+)\/(?:transitions|actions)\//.exec(path)?.[1];
  if (!id) return {};
  const etag = (await page.request.get(`/api/events/${id}`)).headers()['etag'];
  return etag ? { 'If-Match': etag } : {};
}

/** POSTs JSON with the CSRF header and, for transitions and actions, the current `If-Match` (T04, T05 and the status actions need it). */
export async function postJson(page: Page, path: string, data: unknown = {}): Promise<APIResponse> {
  const headers = { ...(await csrfHeaders(page)), ...(await currentEtag(page, path)) };
  return page.request.post(path, { data, headers });
}

export function inDays(days: number): string {
  const d = new Date(Date.now() + days * 86_400_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

export async function patchEvent(
  page: Page,
  id: string,
  rev: number,
  data: unknown,
): Promise<APIResponse> {
  return page.request.patch(`/api/events/${id}`, {
    data,
    headers: { ...(await csrfHeaders(page)), 'If-Match': `"${rev}"` },
  });
}

export async function eventOf(page: Page, id: string): Promise<Record<string, any>> {
  return (await page.request.get(`/api/events/${id}`)).json();
}

export async function waitForCleanPoster(page: Page, id: string): Promise<void> {
  await expect
    .poll(
      async () => {
        const event = await eventOf(page, id);
        return event['poster']?.scanStatus === 'clean' && event['poster']?.derivatives !== null;
      },
      { timeout: 120_000, intervals: [2_000] },
    )
    .toBe(true);
}
