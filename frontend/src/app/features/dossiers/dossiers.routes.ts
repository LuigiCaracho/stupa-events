/**
 * Routes of the dossier area: the list (I04), with the open dossier (I07) as its child route so a wide screen shows
 * both side by side. `/dossiers/neu` reuses the list route with `data.newEvent` for the dialog (see feature-routes.ts).
 */
import type { Routes } from '@angular/router';
import { pendingChangesGuard } from '@core/auth/pending-changes.guard';
import { DossierDetailComponent } from './detail/dossier-detail.component';
import { DossierListComponent } from './list/dossier-list.component';

export default [
  {
    path: '',
    component: DossierListComponent,
    children: [
      { path: ':id', component: DossierDetailComponent, canDeactivate: [pendingChangesGuard] },
      {
        path: ':id/nachbereitung',
        component: DossierDetailComponent,
        data: { tab: 'followup' },
        canDeactivate: [pendingChangesGuard],
      },
    ],
  },
] satisfies Routes;
