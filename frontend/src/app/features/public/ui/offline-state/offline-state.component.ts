/** The offline state of a public page (P14): "Du bist offline." and the way to the last loaded days under Heute. */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { LinkButtonComponent } from '../link-button/link-button.component';

@Component({
  selector: 'app-offline-state',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, EmptyStateComponent, LinkButtonComponent],
  template: `
    <app-empty-state
      plain
      [level]="level()"
      icon="alert"
      [heading]="'public.offline.heading' | t"
      [body]="'public.offline.body' | t"
    >
      <a appLinkButton="tonal" routerLink="/">{{ 'public.offline.toToday' | t }}</a>
    </app-empty-state>
  `,
})
export class OfflineStateComponent {
  readonly level = input(1);
}
