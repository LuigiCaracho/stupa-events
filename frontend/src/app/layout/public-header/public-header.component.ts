/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/layout/public-header/public-header.component.ts */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ThemeService } from '@core/theme/theme.service';
import { IconComponent } from '@stupa-makers/ui-kit';

/**
 * The top bar of the public frame (landing page, 404 while signed out): the wordmark,
 * the appearance toggle and "Anmelden". A signed-out visitor has no account menu, so the
 * appearance toggle stays in the bar. The language switch returns with stage B.
 */
@Component({
  selector: 'app-public-header',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, IconComponent],
  templateUrl: './public-header.component.html',
  styleUrl: './public-header.component.scss',
})
export class PublicHeaderComponent {
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);

  /** Black type on light, white type on dark: both are official CD variants. */
  readonly logoSrc = computed(() => `assets/logos/stupa-wordmark-${this.theme.resolved()}.svg`);
  /** The mark alone, for a phone, where the wordmark does not fit beside the controls. */
  readonly markSrc = 'assets/logos/stupa-mark.svg';

  login(): void {
    this.auth.login();
  }
}
