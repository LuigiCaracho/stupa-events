/** Routes of the task area (`/aufgaben`). */
import type { Routes } from '@angular/router';
import { TasksComponent } from './tasks.component';

export default [{ path: '', component: TasksComponent }] satisfies Routes;
