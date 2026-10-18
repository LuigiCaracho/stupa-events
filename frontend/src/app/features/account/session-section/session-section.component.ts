/**
 * I27 part "Sitzungen": ends all other sessions of the signed-in person after a confirmation.
 * The running session stays; the other devices must log in again, which re-reads the IdP groups.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { ButtonComponent, DialogComponent, ToastService } from '@stupa-makers/ui-kit';
import { SessionsApi } from '../../admin/api/sessions-api.service';
import { problemMessage } from '../../dossiers/api/problem-message';

@Component({
  selector: 'app-session-section',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, DialogComponent],
  templateUrl: './session-section.component.html',
  styleUrl: './session-section.component.scss',
})
export class SessionSectionComponent {
  private readonly api = inject(SessionsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  protected readonly confirming = signal(false);
  protected readonly busy = signal(false);

  protected revoke(): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api.revokeOwn().subscribe({
      next: ({ revoked }) => {
        this.busy.set(false);
        this.confirming.set(false);
        this.toast.success(this.i18n.translate('account.sessions.done', { n: revoked }));
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
