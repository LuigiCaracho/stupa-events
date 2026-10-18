/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/app.routes.ts (rewritten) */
/**
 * Routing skeleton. Rewritten from the workflow tool:
 * one `ShellComponent` frames every route. `authGuard` protects the OIDC areas; the
 * feature areas come from `feature-routes.ts`. Route data: `title` (i18n key, breadcrumb
 * and tab), `wide`, `fab`, `footer` and `chrome: false`, read by the shell.
 */
import type { Routes } from '@angular/router';
import { authGuard } from '@core/auth/auth.guard';
import { homeRedirectGuard } from '@core/auth/home-redirect.guard';
import { FEATURE_ROUTES } from './feature-routes';
import { ShellComponent } from './layout/shell.component';

export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    children: [
      {
        path: '',
        pathMatch: 'full',
        canActivate: [homeRedirectGuard],
        data: { footer: true },
        loadComponent: () => import('./pages/home/home.component').then((m) => m.HomeComponent),
      },
      {
        path: 'login',
        data: { title: 'login.title', chrome: false },
        loadComponent: () => import('./pages/login/login.component').then((m) => m.LoginComponent),
      },
      ...FEATURE_ROUTES,
      {
        path: 'konto',
        data: { title: 'nav.account' },
        canActivate: [authGuard],
        loadComponent: () =>
          import('./pages/account/account.component').then((m) => m.AccountComponent),
      },
      {
        path: 'forbidden',
        data: { title: 'forbidden.heading' },
        loadComponent: () =>
          import('./pages/forbidden.component').then((m) => m.ForbiddenComponent),
      },
      {
        path: '**',
        loadComponent: () =>
          import('./pages/not-found.component').then((m) => m.NotFoundComponent),
      },
    ],
  },
];
