/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/pwa/ngsw-navigation.spec.ts */
/**
 * The service worker must not answer for paths the server renders itself.
 *
 * This exists because it did in the workflow tool. `navigationUrls` claims `/**`, so the
 * worker served the Angular shell for `/s/<token>` and the router turned a working share
 * link into the app's own 404 page. Here the server-rendered paths are the public
 * landing pages (`/e/`, `/k/`), the calendar feeds and the tiles (PLAN 9.1). nginx proxying that path to the API was necessary and not
 * sufficient: the request never left the browser.
 *
 * The check is on the config rather than on a running worker, because that is where the
 * mistake is made and it holds without a build.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

interface NgswConfig {
  navigationUrls: string[];
}

/** Paths the SERVER answers with its own HTML. None may reach the Angular router. */
const SERVER_RENDERED = [
  '/api/**',
  '/.well-known/**',
  '/ics/**',
  '/e/**',
  '/k/**',
  '/abo/**',
  '/bestaetigen/**',
  '/tiles/**',
  '/sitemap.xml',
  '/robots.txt',
];

function config(): NgswConfig {
  // Four levels up from src/app/core/pwa to the project root.
  const path = join(__dirname, '..', '..', '..', '..', 'ngsw-config.json');
  return JSON.parse(readFileSync(path, 'utf8')) as NgswConfig;
}

describe('service worker navigation URLs', () => {
  it.each(SERVER_RENDERED)('leaves %s to the server', (pattern) => {
    expect(config().navigationUrls).toContain(`!${pattern}`);
  });

  it('still claims everything else, so a deep link into the app works offline', () => {
    expect(config().navigationUrls).toContain('/**');
  });
});
