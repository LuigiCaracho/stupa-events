/**
 * The footer of the public frame: the co-branding line and the links Impressum, Datenschutz, "Kalender abonnieren" and
 * "Intern anmelden" (a signed-in person gets "Zum Dossier" instead), and the switch between Deutsch and English.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import type { Locale } from '@core/i18n/translations';
import { TranslatePipe } from '@core/i18n/translate.pipe';

/** Language names stay in their own language, so a person who cannot read the page can still find theirs. */
const LANGUAGES: readonly { locale: Locale; name: string }[] = [
  { locale: 'de', name: 'Deutsch' },
  { locale: 'en', name: 'English' },
];

@Component({
  selector: 'app-site-footer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe],
  templateUrl: './site-footer.component.html',
  styleUrl: './site-footer.component.scss',
})
export class SiteFooterComponent {
  readonly auth = inject(AuthService);
  protected readonly i18n = inject(I18nService);
  protected readonly languages = LANGUAGES;

  login(): void {
    this.auth.login('/dossiers');
  }
}
