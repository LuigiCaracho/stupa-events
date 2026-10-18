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
  await confirm.waitFor({ state: 'visible', timeout: 5_000 }).then(() => confirm.click(), () => undefined);
  await expect.poll(async () => (await page.request.get('/api/auth/me')).status()).toBe(401);
}

export async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  const cookies = await page.context().cookies();
  const token = cookies.find((c) => c.name === 'XSRF-TOKEN')?.value;
  return token ? { 'X-XSRF-TOKEN': token } : {};
}

export async function postJson(page: Page, path: string, data: unknown = {}): Promise<APIResponse> {
  return page.request.post(path, { data, headers: await csrfHeaders(page) });
}

export function inDays(days: number): string {
  const d = new Date(Date.now() + days * 86_400_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}
