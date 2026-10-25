/**
 * B4 acceptance, update flow (C contract 6.4): a new build appears on the server; within the check the page offers
 * "Neu laden" (no way to dismiss it), the click reloads and the new version runs. The stack is a writable copy of the
 * production build behind the throwaway nginx (`scripts/pwa-update-stack.sh start`, port 8084). The "new version" is a
 * marker comment in `index.html` with its SHA-1 in the `hashTable` of `ngsw.json`, the way the Angular worker verifies a
 * file, and a new `timestamp`.
 */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { loadControlled, stateOf } from './support/service-worker';

const BASE_URL = process.env['PWA_BASE_URL'] ?? 'http://127.0.0.1:8084';
const DIST = process.env['PWA_DIST'] ?? '/tmp/ev-pwa-dist';
const MARKER = '<!-- ev-pwa-update-test -->';

test.use({ baseURL: BASE_URL, locale: 'de-DE', serviceWorkers: 'allow' });

function publishNewVersion(): void {
  const indexPath = join(DIST, 'index.html');
  const html = readFileSync(indexPath, 'utf8');
  if (html.includes(MARKER))
    throw new Error('the stack already serves the new version, reset it first');
  const next = html.replace('</body>', `${MARKER}</body>`);
  writeFileSync(indexPath, next);
  const manifestPath = join(DIST, 'ngsw.json');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as {
    timestamp: number;
    hashTable: Record<string, string>;
  };
  expect(manifest.hashTable['/index.html'], 'index.html is hashed by the worker').toMatch(
    /^[0-9a-f]{40}$/,
  );
  manifest.hashTable['/index.html'] = createHash('sha1').update(next).digest('hex');
  manifest.timestamp += 1;
  writeFileSync(manifestPath, JSON.stringify(manifest));
}

test('a new build raises the prompt, the reload runs the new version', async ({ page }) => {
  test.setTimeout(240_000);
  await loadControlled(page, '/');
  const before = await stateOf(page);
  await expect(page.getByText('Eine neue Version der App ist verfügbar.')).toHaveCount(0);

  publishNewVersion();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));

  const prompt = page
    .getByRole('status')
    .filter({ hasText: 'Eine neue Version der App ist verfügbar.' });
  await expect(prompt).toBeVisible({ timeout: 60_000 });
  await expect(prompt.getByRole('button')).toHaveText(['Neu laden']);

  await prompt.getByRole('button', { name: 'Neu laden' }).click();
  await page.waitForLoadState('load');
  await expect(page.getByText('Eine neue Version der App ist verfügbar.')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Heute am Campus' }).first()).toBeVisible();
  const after = await stateOf(page);
  expect(after).not.toEqual(before);
  const served = await page.evaluate(() =>
    fetch('/index.html', { cache: 'no-store' }).then((r) => r.text()),
  );
  expect(served).toContain(MARKER);
});
