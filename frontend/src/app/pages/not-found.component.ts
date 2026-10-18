/** 404 page: "missing" and "not allowed" read the same, so the page leaks nothing. */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { ErrorPageComponent } from './error-page.component';

@Component({
  selector: 'app-not-found',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ErrorPageComponent],
  template: `<app-error-page heading="notFound.heading" body="notFound.body" code="404" />`,
})
export class NotFoundComponent {}
