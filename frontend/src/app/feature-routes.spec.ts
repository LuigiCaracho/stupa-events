import type { Routes } from '@angular/router';
import { FEATURE_ROUTES } from './feature-routes';

describe('FEATURE_ROUTES', () => {
  const byPath = (path: string) => FEATURE_ROUTES.find((r) => r.path === path);

  it('loads the lazy routes of every feature area behind the auth guard', async () => {
    for (const route of FEATURE_ROUTES) {
      expect(route.canActivate?.length).toBeGreaterThanOrEqual(1);
      const loaded = await (route.loadChildren as () => Promise<{ default: unknown[] }>)();
      expect(Array.isArray(loaded.default)).toBe(true);
    }
  });

  it('guards the admin area by session and by permission', () => {
    expect(byPath('verwaltung')?.canActivate).toHaveLength(2);
    expect(byPath('verwaltung')?.data?.['wide']).toBe(true);
  });

  it('flags the new-event route and serves the list and the dossier page as siblings', async () => {
    expect(byPath('dossiers/neu')?.data?.['newEvent']).toBe(true);
    expect(byPath('dossiers/:id')).toBeUndefined();
    const loaded = await (byPath('dossiers')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(loaded.default.map((r) => r.path)).toEqual(['', ':id']);
    expect(loaded.default[0].children).toBeUndefined();
    expect(loaded.default[1].canDeactivate).toHaveLength(1);
  });

  it('keeps Archiv, Formate and Bibliothek behind the session guard in the wide frame', () => {
    for (const path of ['archiv', 'formate', 'bibliothek']) {
      expect(byPath(path)?.canActivate).toHaveLength(1);
      expect(byPath(path)?.data?.['wide']).toBe(true);
    }
  });

  it('has no board, task, calendar or follow-up route any more', async () => {
    for (const path of ['aufgaben', 'pipeline', 'kalender']) expect(byPath(path)).toBeUndefined();
    const loaded = await (byPath('dossiers')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(loaded.default.some((r) => r.path?.includes('nachbereitung'))).toBe(false);
  });

  it('serves the archive page and the read-only archive dossier, the format as a child and the library item', async () => {
    const archive = await (byPath('archiv')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(archive.default.map((r) => r.path)).toEqual(['', ':id']);
    const formats = await (byPath('formate')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(formats.default[0].children?.[0].path).toBe(':slug');
    const library = await (byPath('bibliothek')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(library.default.map((r) => r.path)).toEqual(['', ':kind/:id']);
  });
});
