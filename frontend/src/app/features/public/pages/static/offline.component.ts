/** P14 Offline: the page the app shows when there is no network; the last loaded days are under "Heute". */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { usePageTitle } from '../../ui/page-title';

@Component({
  selector: 'app-offline-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, EmptyStateComponent, LinkButtonComponent],
  template: `
    <app-empty-state
      plain
      level="1"
      icon="alert"
      [heading]="'public.offline.heading' | t"
      [body]="'public.offline.body' | t"
    >
      <a appLinkButton="tonal" routerLink="/">{{ 'public.offline.toToday' | t }}</a>
    </app-empty-state>
  `,
  styleUrl: './static.scss',
})
export class OfflinePageComponent {
  constructor() {
    const i18n = inject(I18nService);
    usePageTitle(() => i18n.translate('public.offline.title'));
  }
}
