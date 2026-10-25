/**
 * B4 acceptance, offline (C contract 6.4): with the service worker in control, "Heute" and the last opened event stay
 * readable without a network and say "Offline, Stand HH:MM"; an event that was never opened shows the offline state. Runs
 * against the production build behind nginx (`E2E_BASE_URL`, default 8081).
 */
import { expect, test } from '@playwright/test';
import { loadControlled } from './support/service-worker';

const BASE_URL = process.env['E2E_BASE_URL'] ?? 'http://127.0.0.1:8081';

test.use({ baseURL: BASE_URL, locale: 'de-DE', serviceWorkers: 'allow' });

test('Heute and the last opened event read offline, a new event shows the offline state', async ({
  page,
  context,
  request,
}) => {
  test.setTimeout(240_000);
  const list = (await (await request.get('/api/public/events?limit=5')).json()).items as {
    slug: string;
    title: string;
  }[];
  expect(list.length).toBeGreaterThan(1);
  const [opened, never] = list;

  await loadControlled(page, '/');
  await page.goto(`/e/${opened.slug}`);
  await expect(page.getByRole('heading', { name: opened.title, level: 1 })).toBeVisible();
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Heute am Campus' }).first()).toBeVisible();

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Heute am Campus' }).first()).toBeVisible();
  await expect(page.getByText(/^Offline, Stand \d\d:\d\d$/)).toBeVisible();
  await expect(page.locator('main a[href^="/e/"]').first()).toBeVisible();

  await page.goto(`/e/${opened.slug}`);
  await expect(page.getByRole('heading', { name: opened.title, level: 1 })).toBeVisible();

  await page.goto(`/e/${never.slug}`);
  await expect(page.getByRole('heading', { name: 'Du bist offline.' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Zu Heute' })).toBeVisible();

  await context.setOffline(false);
});
