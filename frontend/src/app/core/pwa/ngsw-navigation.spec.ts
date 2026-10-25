/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/pwa/ngsw-navigation.spec.ts */
/**
 * The service worker must not answer for paths the server renders itself.
 *
 * This exists because it did in the workflow tool. `navigationUrls` claims `/**`, so the
 * worker served the Angular shell for `/s/<token>` and the router turned a working share
 * link into the app's own 404 page. Here the server-rendered paths are the category landing pages (`/k/`), the calendar
 * feeds, the token pages and the tiles (PLAN 9.1). The event page `/e/<slug>` is the exception (C contract 5.6): the SPA knows
 * the route, so the worker answers it from the app shell and the last opened event reads offline; the server HTML of
 * `/e/` is for crawlers and link previews, which have no worker.
 *
 * The data groups (B4) keep "Heute" and opened events readable offline. Map answers and tiles stay out of every cache.
 *
 * The check is on the config rather than on a running worker, because that is where the
 * mistake is made and it holds without a build.
 */
import { matches, ngswConfig as config } from '../../../testing/ngsw-config';

/** Paths the SERVER answers with its own HTML. None may reach the Angular router. */
const SERVER_RENDERED = [
  '/api/**',
  '/.well-known/**',
  '/ics/**',
  '/k/**',
  '/abo/**',
  '/bestaetigen/**',
  '/tiles/**',
  '/sitemap.xml',
  '/robots.txt',
];

/** Paths the SPA owns although the server also renders a page for crawlers. */
const SPA_OWNED = ['/e/**'];

describe('service worker navigation URLs', () => {
  it.each(SERVER_RENDERED)('leaves %s to the server', (pattern) => {
    expect(config().navigationUrls).toContain(`!${pattern}`);
  });

  it.each(SPA_OWNED)('answers %s from the app shell', (pattern) => {
    expect(config().navigationUrls).not.toContain(`!${pattern}`);
  });

  it('still claims everything else, so a deep link into the app works offline', () => {
    expect(config().navigationUrls).toContain('/**');
  });
});

describe('service worker data groups', () => {
  const urls = (): string[] => config().dataGroups.flatMap((g) => g.urls);
  const hit = (path: string): string[] => urls().filter((p) => matches(p, path));

  it('keep Heute and one opened event, freshness first', () => {
    const groups = Object.fromEntries(config().dataGroups.map((g) => [g.name, g]));
    expect(groups['today'].urls).toEqual(['/api/public/today']);
    expect(groups['events'].urls).toEqual(['/api/public/events/*']);
    for (const g of Object.values(groups)) {
      expect(g.cacheConfig).toMatchObject({ strategy: 'freshness', timeout: '3s', maxAge: '1d' });
    }
  });

  it.each([
    '/api/public/events',
    '/api/public/map/events',
    '/api/public/campus/buildings',
    '/api/public/campus/events',
    '/api/public/calendar',
    '/api/auth/me',
    '/tiles/world.pmtiles',
    '/tiles/reutlingen.pmtiles',
    '/map/maplibre-gl.mjs',
  ])('never cache %s', (path) => {
    expect(hit(path)).toEqual([]);
  });

  it.each(['/api/public/today', '/api/public/events/kinoabend'])('caches %s', (path) => {
    expect(hit(path).length).toBe(1);
  });
});
