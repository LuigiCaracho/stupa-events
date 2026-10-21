/** Routes of the archive: the search page (I20) and the read-only view of an archived dossier of another organization. */
import type { Routes } from '@angular/router';
import { ArchiveEventComponent } from './event/archive-event.component';
import { ArchivePageComponent } from './page/archive-page.component';

export default [
  { path: '', component: ArchivePageComponent },
  { path: ':id', component: ArchiveEventComponent },
] satisfies Routes;
