/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/bottom-bar/bottom-bar.component.ts */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { IconComponent } from '@stupa-makers/ui-kit';
import { NotificationsStore } from '../../features/notifications/notifications.store';
import { I18nService } from '@core/i18n/i18n.service';
import { SideSheetComponent } from '@shared/ui/side-sheet/side-sheet.component';
import { BOTTOM_BAR_KEYS, NavService, type NavItem } from '../nav.service';

/**
 * The phone navigation (viewport <= 768px): Events, Archiv, Formate and Bibliothek, the bell, and a "Mehr" sheet
 * (`shared/ui/side-sheet`) with Verwaltung (with a permission) and Konto.
 *
 * The shell shows the bar only under the phone media query (`MEDIA.phone`).
 */
@Component({
  selector: 'app-bottom-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, TranslatePipe, IconComponent, SideSheetComponent],
  templateUrl: './bottom-bar.component.html',
  styleUrl: './bottom-bar.component.scss',
})
export class BottomBarComponent {
  private readonly nav = inject(NavService);
  private readonly i18n = inject(I18nService);
  protected readonly store = inject(NotificationsStore);
  protected readonly bellLabel = computed(() =>
    this.i18n.translate('bell.aria', { count: this.store.count() }),
  );

  readonly barItems = computed<NavItem[]>(() => {
    const visible = this.nav.visible();
    return BOTTOM_BAR_KEYS.map((key) => visible.find((i) => i.key === key)).filter(
      (i): i is NavItem => !!i,
    );
  });
  readonly moreItems = computed<NavItem[]>(() =>
    this.nav.visible().filter((i) => !BOTTOM_BAR_KEYS.includes(i.key)),
  );

  private readonly router = inject(Router);
  protected readonly moreOpen = signal(false);

  /** The current page is one that only the sheet links to. */
  protected moreActive(): boolean {
    return this.moreItems().some((i) => this.router.url.startsWith(i.path));
  }
}
