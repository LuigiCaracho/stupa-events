/**
 * Routes of the dossier area: the event list with its calendar (the start page) and the dossier page. `/dossiers/neu`
 * reuses the list route with `data.newEvent` for the dialog (see feature-routes.ts).
 */
import type { Routes } from '@angular/router';
import { pendingChangesGuard } from '@core/auth/pending-changes.guard';
import { DossierDetailComponent } from './detail/dossier-detail.component';
import { DossierListComponent } from './list/dossier-list.component';

export default [
  { path: '', component: DossierListComponent },
  { path: ':id', component: DossierDetailComponent, canDeactivate: [pendingChangesGuard] },
] satisfies Routes;
