/** Route of the dossier list; `/dossiers/neu` reuses it with `data.newEvent` for the dialog (see feature-routes.ts). */
import type { Routes } from '@angular/router';
import { DossierListComponent } from './list/dossier-list.component';

export default [{ path: '', component: DossierListComponent }] satisfies Routes;
