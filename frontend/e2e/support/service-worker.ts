/** Helpers of the PWA specs: wait until the Angular service worker controls the page and has installed its version. */
import { type Page, expect } from '@playwright/test';

const READY_MS = 90_000;

/**
 * Loads `path` and waits until the worker controls the page and reports a normal state with a latest version. The
 * worker registers when the app is stable or after 30 s; a reload hands the first page to it.
 */
export async function loadControlled(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.waitForFunction(
    () => 'serviceWorker' in navigator && !!navigator.serviceWorker,
    undefined,
    {
      timeout: READY_MS,
    },
  );
  await expect
    .poll(
      async () =>
        page.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => !!r?.active)),
      {
        timeout: READY_MS,
      },
    )
    .toBe(true);
  await expect.poll(() => stateOf(page), { timeout: READY_MS }).toMatch(/Driver state: NORMAL/);
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller, undefined, {
    timeout: READY_MS,
  });
  await page.waitForLoadState('networkidle');
}

/** The text of `/ngsw/state` ("Driver state: NORMAL", the latest manifest hash, the cached groups). */
export function stateOf(page: Page): Promise<string> {
  return page.evaluate(() => fetch('/ngsw/state', { cache: 'no-store' }).then((r) => r.text()));
}
