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

  it('flags the new-event route and serves the dossier as a child of the list', async () => {
    expect(byPath('dossiers/neu')?.data?.['newEvent']).toBe(true);
    expect(byPath('dossiers/:id')).toBeUndefined();
    const loaded = await (byPath('dossiers')?.loadChildren as () => Promise<{ default: Routes }>)();
    const child = loaded.default[0].children?.[0];
    expect(child?.path).toBe(':id');
    expect(child?.canDeactivate).toHaveLength(1);
  });

  it('adds Kalender, Archiv, Formate and Bibliothek behind the session guard in the wide frame', async () => {
    for (const path of ['kalender', 'archiv', 'formate', 'bibliothek']) {
      expect(byPath(path)?.canActivate).toHaveLength(1);
      expect(byPath(path)?.data?.['wide']).toBe(true);
    }
  });

  it('opens the follow-up tab by its own child route of the dossier list', async () => {
    const loaded = await (byPath('dossiers')?.loadChildren as () => Promise<{ default: Routes }>)();
    const child = loaded.default[0].children?.find((r) => r.path === ':id/nachbereitung');
    expect(child?.data?.['tab']).toBe('followup');
    expect(child?.canDeactivate).toHaveLength(1);
  });

  it('serves the archive page and the read-only archive dossier, the format as a child and the library item', async () => {
    const archive = await (byPath('archiv')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(archive.default.map((r) => r.path)).toEqual(['', ':id']);
    const formats = await (byPath('formate')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(formats.default[0].children?.[0].path).toBe(':slug');
    const library = await (byPath('bibliothek')?.loadChildren as () => Promise<{ default: Routes }>)();
    expect(library.default.map((r) => r.path)).toEqual(['', ':kind/:id']);
  });

  it('gives the pipeline the wide frame and the fab', () => {
    expect(byPath('pipeline')?.data).toEqual({ title: 'nav.pipeline', wide: true, fab: true });
  });
});
