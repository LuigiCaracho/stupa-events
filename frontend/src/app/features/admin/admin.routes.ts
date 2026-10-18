/** Routes of the admin area (`/verwaltung`): one frame with tabs, one lazy page per tab, each behind its permission. */
import type { Routes } from '@angular/router';
import { permissionGuard } from '@core/auth/permission.guard';
import { AdminFrameComponent } from './admin-frame/admin-frame.component';
import { adminLandingGuard } from './admin-tabs';

export default [
  {
    path: '',
    component: AdminFrameComponent,
    children: [
      { path: '', pathMatch: 'full', canActivate: [adminLandingGuard], children: [] },
      {
        path: 'kategorien',
        data: { title: 'admin.tab.categories' },
        canActivate: [permissionGuard('taxonomy.manage')],
        loadComponent: () =>
          import('./taxonomy/categories/categories.component').then((m) => m.CategoriesComponent),
      },
      {
        path: 'orte',
        data: { title: 'admin.tab.venues' },
        canActivate: [permissionGuard('venue.manage')],
        loadComponent: () =>
          import('./taxonomy/venues/venues.component').then((m) => m.VenuesComponent),
      },
      {
        path: 'organisationen',
        data: { title: 'admin.tab.organizations' },
        canActivate: [permissionGuard('taxonomy.manage')],
        loadComponent: () =>
          import('./taxonomy/organizations/organizations.component').then(
            (m) => m.OrganizationsComponent,
          ),
      },
      {
        path: 'zuordnungen',
        data: { title: 'admin.tab.mappings' },
        canActivate: [permissionGuard('admin.mappings')],
        loadComponent: () =>
          import('./mappings/mappings.component').then((m) => m.MappingsComponent),
      },
      { path: 'taxonomie', redirectTo: 'kategorien' },
      { path: 'gruppen', redirectTo: 'zuordnungen' },
    ],
  },
] satisfies Routes;
