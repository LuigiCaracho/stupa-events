/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/app.routes.ts (rewritten) */
/**
 * Routing skeleton. Rewritten from the workflow tool:
 * one `ShellComponent` frames every route. `authGuard` protects the OIDC areas; the
 * public site comes from `features/public/public.routes.ts` (`/` is no redirect any more), the
 * feature areas from `feature-routes.ts`. Route data: `title` (i18n key, breadcrumb
 * and tab), `wide`, `footer`, `frame: 'public'` and `chrome: false`, read by the shell.
 */
import type { Routes } from '@angular/router';
import { authGuard } from '@core/auth/auth.guard';
import { FEATURE_ROUTES } from './feature-routes';
import { PUBLIC_DATA, PUBLIC_ROUTES } from './features/public/public.routes';
import { ShellComponent } from './layout/shell.component';

export const routes: Routes = [
  {
    path: '',
    component: ShellComponent,
    children: [
      ...PUBLIC_ROUTES,
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
        data: { ...PUBLIC_DATA, title: 'notFound.heading' },
        loadComponent: () => import('./pages/not-found.component').then((m) => m.NotFoundComponent),
      },
    ],
  },
];
