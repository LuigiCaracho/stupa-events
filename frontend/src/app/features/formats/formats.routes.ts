/** Routes of the formats: the list (I18) with the open format as its child route, like the dossier list. */
import type { Routes } from '@angular/router';
import { FormatDetailComponent } from './detail/format-detail.component';
import { FormatListComponent } from './list/format-list.component';

export default [
  {
    path: '',
    component: FormatListComponent,
    children: [{ path: ':slug', component: FormatDetailComponent }],
  },
] satisfies Routes;
