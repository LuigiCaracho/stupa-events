/** 404 page: "missing" and "not allowed" read the same, so the page leaks nothing. Public frame, with the way to the start page. */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { LinkButtonComponent } from '../features/public/ui/link-button/link-button.component';
import { usePageTitle } from '../features/public/ui/page-title';

@Component({
  selector: 'app-not-found',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, EmptyStateComponent, LinkButtonComponent],
  template: `
    <app-empty-state plain level="1" code="404" [heading]="'notFound.heading' | t" [body]="'notFound.body' | t">
      <a appLinkButton="tonal" routerLink="/">{{ 'public.notFound.home' | t }}</a>
    </app-empty-state>
  `,
})
export class NotFoundComponent {
  constructor() {
    const i18n = inject(I18nService);
    usePageTitle(() => i18n.translate('notFound.heading'));
  }
}
