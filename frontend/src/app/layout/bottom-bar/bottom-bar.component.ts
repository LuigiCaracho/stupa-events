/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/bottom-bar/bottom-bar.component.ts */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { IconComponent } from '@stupa-makers/ui-kit';
import { BOTTOM_BAR_KEYS, NavService, type NavItem } from '../nav.service';

/**
 * The phone navigation (viewport <= 768px): Aufgaben, Dossiers and Konto. Later
 * milestones add entries and a "Mehr" sheet (`shared/ui/side-sheet`) once more than four
 * areas exist.
 *
 * The shell shows the bar only under the phone media query (`MEDIA.phone`).
 */
@Component({
  selector: 'app-bottom-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, TranslatePipe, IconComponent],
  templateUrl: './bottom-bar.component.html',
  styleUrl: './bottom-bar.component.scss',
})
export class BottomBarComponent {
  private readonly nav = inject(NavService);

  readonly barItems = computed<NavItem[]>(() => {
    const visible = this.nav.visible();
    return BOTTOM_BAR_KEYS.map((key) => visible.find((i) => i.key === key)).filter(
      (i): i is NavItem => !!i,
    );
  });
}
