/**
 * "Verwaltungslink anfordern": an address field and one button. The answer is always the same sentence, whether the
 * address is known or not (B3 contract 3.4); only a failed ALTCHA check, the rate limit or a network error show
 * something else. The ALTCHA proof is solved on the click, so the form has no widget.
 */
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { NoteComponent } from '@shared/ui/note/note.component';
import { ButtonComponent, InputComponent } from '@stupa-makers/ui-kit';
import { firstValueFrom } from 'rxjs';
import { SubscriptionsApi } from '../../api/subscriptions-api.service';
import { subscriptionErrorOf } from '../../api/subscription-error';
import { isPlausibleEmail } from '../../model/questionnaire-state';
import { AltchaService } from '../altcha.service';
import { errorText } from '../error-text';

@Component({
  selector: 'app-manage-link-form',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, TranslatePipe, ButtonComponent, InputComponent, NoteComponent],
  templateUrl: './manage-link-form.component.html',
  styleUrl: './manage-link-form.component.scss',
})
export class ManageLinkFormComponent {
  private readonly api = inject(SubscriptionsApi);
  private readonly altcha = inject(AltchaService);
  private readonly i18n = inject(I18nService);

  protected readonly email = signal('');
  protected readonly busy = signal(false);
  protected readonly sent = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly emailError = signal('');

  protected async submit(): Promise<void> {
    if (this.busy()) return;
    this.sent.set(false);
    this.error.set(null);
    const email = this.email().trim();
    if (!isPlausibleEmail(email)) {
      this.emailError.set(this.i18n.translate('public.start.emailInvalid'));
      return;
    }
    this.emailError.set('');
    this.busy.set(true);
    try {
      const solution = (await this.altcha.solve()) ?? '';
      await firstValueFrom(this.api.requestManageLink(email, solution));
      this.sent.set(true);
    } catch (err) {
      const { key, params } = errorText(subscriptionErrorOf(err));
      this.error.set(this.i18n.translate(key as TranslationKey, params));
    } finally {
      this.busy.set(false);
    }
  }
}
