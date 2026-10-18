import type { Route } from '@angular/router';
import routes from './admin.routes';

describe('admin routes', () => {
  const children = routes[0].children as Route[];

  it('lazy-loads every tab page', async () => {
    const loaders = children.filter((r) => r.loadComponent);
    expect(loaders.map((r) => r.path)).toEqual(['kategorien', 'orte', 'organisationen', 'zuordnungen']);
    for (const route of loaders) expect(await (route.loadComponent as () => Promise<unknown>)()).toBeDefined();
  });

  it('guards every tab page by a permission', () => {
    for (const route of children.filter((r) => r.loadComponent)) expect(route.canActivate).toHaveLength(1);
  });

  it('keeps the old paths as redirects', () => {
    expect(children.filter((r) => r.redirectTo).map((r) => [r.path, r.redirectTo])).toEqual([
      ['taxonomie', 'kategorien'],
      ['gruppen', 'zuordnungen'],
    ]);
  });
});
