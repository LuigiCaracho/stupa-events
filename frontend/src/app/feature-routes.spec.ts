import { FEATURE_ROUTES } from './feature-routes';

describe('FEATURE_ROUTES', () => {
  const byPath = (path: string) => FEATURE_ROUTES.find((r) => r.path === path);

  it('loads the lazy routes of every feature area behind the auth guard', async () => {
    for (const route of FEATURE_ROUTES) {
      expect(route.canActivate).toHaveLength(1);
      const loaded = await (route.loadChildren as () => Promise<{ default: unknown[] }>)();
      expect(Array.isArray(loaded.default)).toBe(true);
    }
  });

  it('puts the new-event route before the :id route and flags it', () => {
    const paths = FEATURE_ROUTES.map((r) => r.path);
    expect(paths.indexOf('dossiers/neu')).toBeLessThan(paths.indexOf('dossiers/:id'));
    expect(byPath('dossiers/neu')?.data?.['newEvent']).toBe(true);
    expect(byPath('dossiers/:id')?.data?.['parent']).toEqual(['dossiers']);
  });
});
