/**
 * The top bar of the public frame: the mark with the site title, the navigation Heute, Suche, Kalender, Abos (from
 * `narrow`; a phone has the bottom bar instead), the search pill (from `wide`), the appearance toggle and either
 * "Anmelden" (nobody signed in) or "Zum Dossier" (a signed-in person who opened a public page).
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ThemeService } from '@core/theme/theme.service';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { IconComponent } from '@stupa-makers/ui-kit';
import { PUBLIC_NAV } from '../public-nav';

@Component({
  selector: 'app-public-header',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive, TranslatePipe, IconComponent, SearchPillComponent],
  templateUrl: './public-header.component.html',
  styleUrl: './public-header.component.scss',
})
export class PublicHeaderComponent {
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);
  private readonly router = inject(Router);
  readonly items = PUBLIC_NAV;
  readonly markSrc = 'assets/logos/stupa-mark.svg';

  /** After the login a person lands in the dossier list, not back on the public start page. */
  login(): void {
    this.auth.login('/dossiers');
  }

  openSearch(): void {
    void this.router.navigateByUrl('/suche');
  }
}
