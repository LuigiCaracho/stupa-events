/** Routes of the library: the list (I19), and the same page with an open item (`/bibliothek/:kind/:id`). */
import type { Routes } from '@angular/router';
import { LibraryPageComponent } from './page/library-page.component';

export default [
  { path: '', component: LibraryPageComponent },
  { path: ':kind/:id', component: LibraryPageComponent },
] satisfies Routes;
