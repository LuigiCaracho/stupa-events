/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/pwa/ngsw-assets.spec.ts */
/**
 * The service worker must not hash a file that the server generates at runtime.
 *
 * This exists because it did. `/manifest.webmanifest` was in the prefetch group, but
 * nginx answers it from the API with the active site config. The worker checks each
 * hashed file against the hash of the build. The hash never matched, so every new version
 * failed to install (`VERSION_INSTALLATION_FAILED`), no update prompt came, and a reload
 * kept the old version from the cache.
 *
 * The check is on the config rather than on a running worker, because that is where the
 * mistake is made and it holds without a build.
 */
import { matches, ngswConfig as config } from '../../../testing/ngsw-config';

/** Paths that nginx answers from the API, not from the build output. */
const SERVER_GENERATED = ['/manifest.webmanifest'];

describe('service worker asset groups', () => {
  it.each(SERVER_GENERATED)('do not hash %s', (path) => {
    for (const group of config().assetGroups) {
      const patterns = [...(group.resources.files ?? []), ...(group.resources.urls ?? [])];
      expect(patterns.filter((p) => matches(p, path))).toEqual([]);
    }
  });

  it('still prefetch the app shell', () => {
    const app = config().assetGroups.find((g) => g.name === 'app');
    expect(app?.resources.files).toEqual(expect.arrayContaining(['/index.html', '/*.js']));
  });

  it('leave the lazily loaded map library and the tiles out of the prefetch', () => {
    const app = config().assetGroups.find((g) => g.name === 'app');
    for (const path of [
      '/map/maplibre-gl.mjs',
      '/map/maplibre-gl-worker.mjs',
      '/tiles/world.pmtiles',
    ]) {
      expect((app?.resources.files ?? []).filter((p) => matches(p, path))).toEqual([]);
    }
  });

  it('match a pattern the way the worker does', () => {
    expect(matches('/*.js', '/main-abc.js')).toBe(true);
    expect(matches('/*.js', '/a/main.js')).toBe(false);
    expect(matches('/**/*.(svg|png)', '/icons/a.png')).toBe(true);
    expect(matches('/**/*.(svg|png)', '/a.svg')).toBe(true);
    expect(matches('/manifest.webmanifest', '/manifest.webmanifest')).toBe(true);
  });
});
