/** P14 Offline: the page the app shows when there is no network; the last loaded days are under "Heute". */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { OfflineStateComponent } from '../../ui/offline-state/offline-state.component';
import { usePageTitle } from '../../ui/page-title';

@Component({
  selector: 'app-offline-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [OfflineStateComponent],
  template: `<app-offline-state />`,
  styleUrl: './static.scss',
})
export class OfflinePageComponent {
  constructor() {
    const i18n = inject(I18nService);
    usePageTitle(() => i18n.translate('public.offline.title'));
  }
}
