/**
 * The phone navigation of the public frame (viewport <= 768 px): Heute, Suche, Kalender, Abos. Four entries of 44 px
 * touch targets at least, the safe area below, `aria-current` on the open page. The shell shows it only under the
 * phone media query and only in the `public` frame; the signed-in frame keeps its own bar.
 */
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { IconComponent } from '@stupa-makers/ui-kit';
import { PUBLIC_NAV } from '../public-nav';

@Component({
  selector: 'app-public-bottom-bar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, TranslatePipe, IconComponent],
  templateUrl: './public-bottom-bar.component.html',
  styleUrl: './public-bottom-bar.component.scss',
})
export class PublicBottomBarComponent {
  readonly items = PUBLIC_NAV;
}
