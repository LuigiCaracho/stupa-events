/**
 * Feature areas of the signed-in frame (children of the shell route). Each entry shows
 * the lazy routes of its feature area. Paths, titles, guards and layout flags (`wide`, `fab`)
 * stay here, so the shell owns the frame contract. `dossiers/neu` comes before `dossiers/:id`.
 */
import type { Routes } from '@angular/router';
import { authGuard } from '@core/auth/auth.guard';

export const FEATURE_ROUTES: Routes = [
  {
    path: 'aufgaben',
    data: { title: 'nav.tasks', fab: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/tasks/tasks.routes'),
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
    path: 'dossiers/:id',
    data: { title: 'nav.dossiers', parent: ['dossiers'], wide: true },
    canActivate: [authGuard],
    loadChildren: () => import('./features/dossiers/detail.routes'),
  },
];
