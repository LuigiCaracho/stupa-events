/**
 * P08 Bestätigen (`/bestaetigen/:token`, bare frame): the confirmation link of the double-opt-in mail. Opening the page
 * only checks the token (`confirm/preview`, no change); the subscription turns active with the button (POST), so a link
 * scanner that opens the link confirms nothing. The token leaves the address bar as soon as the check is back.
 */
import { Location } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { of } from 'rxjs';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { firstValueFrom } from 'rxjs';
import { SubscriptionsApi } from '../../api/subscriptions-api.service';
import { subscriptionErrorOf } from '../../api/subscription-error';
import { errorText } from '../../ui/error-text';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { usePageTitle } from '../../ui/page-title';
import { joinLabels } from '../../model/questionnaire-state';

type Phase = 'checking' | 'ready' | 'done' | 'invalid';

@Component({
  selector: 'app-confirm-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    LinkButtonComponent,
    NoteComponent,
    SkeletonComponent,
  ],
  templateUrl: './confirm.component.html',
  styleUrl: './confirm.component.scss',
})
export class ConfirmPageComponent {
  private readonly api = inject(SubscriptionsApi);
  private readonly i18n = inject(I18nService);
  private readonly location = inject(Location);

  readonly token = input<string | undefined>();
  private readonly confirmed = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  private readonly preview = rxResource({
    params: () => this.token(),
    stream: ({ params }) => (params ? this.api.confirmPreview(params) : of(null)),
  });

  protected readonly phase = computed<Phase>(() => {
    if (this.confirmed()) return 'done';
    if (this.preview.isLoading()) return 'checking';
    return this.preview.error() || !this.preview.value() ? 'invalid' : 'ready';
  });
  protected readonly sentence = computed(() => {
    const categories = this.preview.value()?.categories ?? [];
    return categories.length > 0
      ? this.i18n.translate('public.confirm.body', { categories: joinLabels(categories) })
      : this.i18n.translate('public.confirm.bodyAny');
  });

  constructor() {
    usePageTitle(() => this.i18n.translate('public.confirm.title'));
    effect(() => {
      if (!this.preview.isLoading() && this.token()) this.location.replaceState('/bestaetigen');
    });
  }

  protected async confirm(): Promise<void> {
    const token = this.token();
    if (!token || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    try {
      await firstValueFrom(this.api.confirm(token));
      this.confirmed.set(true);
    } catch (err) {
      const failure = subscriptionErrorOf(err);
      if (failure.kind === 'invalidToken') this.preview.set(null);
      else this.error.set(this.i18n.translate(errorText(failure).key, errorText(failure).params));
    } finally {
      this.busy.set(false);
    }
  }
}
