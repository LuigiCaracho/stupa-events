/**
 * The footer of the public frame: the co-branding line and the links Impressum, Datenschutz, "Kalender abonnieren" and
 * "Intern anmelden" (a signed-in person gets "Zum Dossier" instead).
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';

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

  login(): void {
    this.auth.login('/dossiers');
  }
}
