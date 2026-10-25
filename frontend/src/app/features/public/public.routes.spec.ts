/** Spec for the public routes: every one forces the public frame, and the start page is no redirect any more. */
import { routes } from '../../app.routes';
import { PUBLIC_ROUTES } from './public.routes';

describe('PUBLIC_ROUTES', () => {
  it('serves the paths of the contract', () => {
    expect(PUBLIC_ROUTES.map((r) => r.path)).toEqual([
      '',
      'suche',
      'kalender',
      'karte',
      'campus',
      'e/:slug',
      'k/:slug',
      'rueckblick',
      'abos',
      'start',
      'bestaetigen/:token',
      'bestaetigen',
      'abo/:token',
      'abo',
      'impressum',
      'datenschutz',
      'offline',
    ]);
  });

  it('forces the public frame with a footer on every route and on the 404', () => {
    const shell = routes[0].children ?? [];
    for (const route of [...PUBLIC_ROUTES, shell.find((r) => r.path === '**')!]) {
      expect(route.data).toMatchObject({ frame: 'public', footer: true });
    }
  });

  it('shows the confirmation page without the site chrome', () => {
    const confirm = PUBLIC_ROUTES.filter((r) => r.path?.startsWith('bestaetigen'));
    expect(confirm).toHaveLength(2);
    confirm.forEach((r) => expect(r.data).toMatchObject({ chrome: false }));
  });

  it('makes the start page a plain page: no guard, no redirect', () => {
    const start = PUBLIC_ROUTES[0];
    expect(start.canActivate).toBeUndefined();
    expect(start.redirectTo).toBeUndefined();
  });

  it('mounts the public routes before the feature areas and the fallback', () => {
    const paths = (routes[0].children ?? []).map((r) => r.path);
    expect(paths.indexOf('suche')).toBeLessThan(paths.indexOf('dossiers'));
    expect(paths[paths.length - 1]).toBe('**');
  });
});
