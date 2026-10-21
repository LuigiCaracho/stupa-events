/** Route of the internal calendar (`/kalender`, M5 contract 7). */
import type { Routes } from '@angular/router';
import { CalendarPageComponent } from './page/calendar-page.component';

export default [{ path: '', component: CalendarPageComponent }] satisfies Routes;
