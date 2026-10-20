/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/nav-rail/nav-rail.component.ts */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { IconComponent } from '@stupa-makers/ui-kit';
import { NotificationsStore } from '../../features/notifications/notifications.store';
import { I18nService } from '@core/i18n/i18n.service';
import { NavService } from '../nav.service';

/**
 * The navigation rail: 96px at the start edge of every signed-in page above the phone
 * width. The mark leads to the start page. Then come the areas the principal may open
 * (RBAC filter in {@link NavService}), a spacer, and the account at the foot.
 */
@Component({
  selector: 'app-nav-rail',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, TranslatePipe, IconComponent],
  templateUrl: './nav-rail.component.html',
  styleUrl: './nav-rail.component.scss',
})
export class NavRailComponent {
  private readonly nav = inject(NavService);
  private readonly i18n = inject(I18nService);
  protected readonly store = inject(NotificationsStore);
  protected readonly bellLabel = computed(() =>
    this.i18n.translate('bell.aria', { count: this.store.count() }),
  );

  readonly mainItems = computed(() => this.nav.visible().filter((i) => i.place === 'main'));
  readonly endItems = computed(() => this.nav.visible().filter((i) => i.place === 'end'));
  readonly markSrc = 'assets/logos/stupa-mark.svg';
}
