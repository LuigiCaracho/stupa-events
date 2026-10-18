/**
 * Feature areas of the signed-in frame (children of the shell route). Each entry shows
 * the lazy routes of its feature area. Paths, titles, guards and layout flags (`wide`, `fab`)
 * stay here, so the shell owns the frame contract. `dossiers/:id` is a child route of the dossier list (list and
 * detail side by side, see `dossiers.routes.ts`); `dossiers/neu` opens the dialog over the list. `verwaltung` adds
 * its permission guard to the session guard.
 */
import type { Routes } from '@angular/router';
import { authGuard } from '@core/auth/auth.guard';
import { permissionGuard } from '@core/auth/permission.guard';
import { ADMIN_PERMISSIONS } from './features/admin/admin-tabs';

export const FEATURE_ROUTES: Routes = [
  {
    path: 'aufgaben',
    data: { title: 'nav.tasks', fab: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/tasks/tasks.routes'),
  },
  {
    path: 'pipeline',
    data: { title: 'nav.pipeline', wide: true, fab: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/pipeline/pipeline.routes'),
  },
  {
    path: 'dossiers/neu',
    data: { title: 'new.title', parent: ['dossiers'], wide: true, newEvent: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/dossiers/dossiers.routes'),
  },
  {
    path: 'dossiers',
    data: { title: 'nav.dossiers', wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/dossiers/dossiers.routes'),
  },
  {
    path: 'verwaltung',
    data: { title: 'nav.admin', wide: true },
    canActivate: [authGuard, permissionGuard(...ADMIN_PERMISSIONS)],
    loadChildren: () => import('./features/admin/admin.routes'),
  },
];
