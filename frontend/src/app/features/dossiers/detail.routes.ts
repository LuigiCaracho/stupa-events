/** Route of one dossier (`/dossiers/:id`); the id arrives as component input. */
import type { Routes } from '@angular/router';
import { DossierDetailComponent } from './detail/dossier-detail.component';

export default [{ path: '', component: DossierDetailComponent }] satisfies Routes;
