/**
 * Feature areas of the signed-in frame (children of the shell route). Each entry shows
 * the lazy routes of its feature area. Paths, titles, guards and layout flags (`wide`)
 * stay here, so the shell owns the frame contract. `dossiers` is the start page (the event list with its
 * calendar), `dossiers/:id` the dossier page (see `dossiers.routes.ts`); `dossiers/neu` opens the dialog over the
 * list (with `?vorlage=<id>` the clone dialog I06). `archiv`, `formate` and `bibliothek` follow. `verwaltung` adds
 * its permission guard to the session guard.
 */
import type { Routes } from '@angular/router';
import { authGuard } from '@core/auth/auth.guard';
import { permissionGuard } from '@core/auth/permission.guard';
import { ADMIN_PERMISSIONS } from './features/admin/admin-tabs';

export const FEATURE_ROUTES: Routes = [
  {
    path: 'dossiers/neu',
    data: { title: 'new.title', parent: ['dossiers'], wide: true, newEvent: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/dossiers/dossiers.routes'),
  },
  {
    path: 'dossiers',
    data: { title: 'nav.events', wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/dossiers/dossiers.routes'),
  },
  {
    path: 'archiv',
    data: { title: 'nav.archive', wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/archive/archive.routes'),
  },
  {
    path: 'formate',
    data: { title: 'nav.formats', wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/formats/formats.routes'),
  },
  {
    path: 'bibliothek',
    data: { title: 'nav.library', wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/library/library.routes'),
  },
  {
    path: 'verwaltung',
    data: { title: 'nav.admin', wide: true },
    canActivate: [authGuard, permissionGuard(...ADMIN_PERMISSIONS)],
    loadChildren: () => import('./features/admin/admin.routes'),
  },
];
