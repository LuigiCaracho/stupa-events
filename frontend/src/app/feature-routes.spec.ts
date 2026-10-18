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

  it('gives the pipeline the wide frame and the fab', () => {
    expect(byPath('pipeline')?.data).toEqual({ title: 'nav.pipeline', wide: true, fab: true });
  });
});
