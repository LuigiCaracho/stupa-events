/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/app.ts */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/** Root component. It holds only the router outlet. ShellComponent provides the layout. */
@Component({
  selector: 'app-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class App {}
