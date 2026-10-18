/** 403 page (`/forbidden`). */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ErrorPageComponent } from './error-page.component';

@Component({
  selector: 'app-forbidden',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ErrorPageComponent],
  template: `<app-error-page heading="forbidden.heading" body="forbidden.body" code="403" />`,
})
export class ForbiddenComponent {}
