/** Account page (`/konto`): who is signed in, which groups, roles and organizations they grant, the session revoke and logout. */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import type { TranslationKey } from '@core/i18n/translations';
import { ROLE_KEYS } from '../../features/admin/admin-labels';
import { SessionSectionComponent } from '../../features/account/session-section/session-section.component';
import { AuthService } from '@core/auth/auth.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { ButtonComponent, CardComponent } from '@stupa-makers/ui-kit';

@Component({
  selector: 'app-account',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    CardComponent,
    PageHeaderComponent,
    SessionSectionComponent,
  ],
  templateUrl: './account.component.html',
  styleUrl: './account.component.scss',
})
export class AccountComponent {
  readonly auth = inject(AuthService);
  private readonly i18n = inject(I18nService);

  protected roleLabel(role: string): string {
    const key = (ROLE_KEYS as Record<string, TranslationKey | undefined>)[role];
    return key ? this.i18n.translate(key) : role;
  }
}
