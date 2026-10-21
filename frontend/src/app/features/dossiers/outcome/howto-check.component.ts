/**
 * "Anleitung geprüft" (M5 contract 3.2): the tick for the howto. Ticking calls `verify-howto`, unticking removes the
 * mark again (not once the dossier is archived). The line below says who checked and when. A dossier without a howto
 * and without a format howto has nothing to check.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { CheckboxComponent, ToastService } from '@stupa-makers/ui-kit';
import { OutcomeApi } from '../api/outcome-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';

@Component({
  selector: 'app-howto-check',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, LocalizedDatePipe, TranslatePipe, CheckboxComponent],
  templateUrl: './howto-check.component.html',
  styleUrl: './howto-check.component.scss',
})
export class HowtoCheckComponent {
  private readonly api = inject(OutcomeApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly changed = output<EventDto>();

  protected readonly busy = signal(false);
  protected readonly verified = computed(() => !!this.event().howtoVerifiedAt);
  protected readonly locked = computed(
    () => !this.canEdit() || this.busy() || (this.verified() && this.event().state === 'archived'),
  );

  protected toggle(checked: boolean): void {
    if (this.busy()) return;
    this.busy.set(true);
    const id = this.event().id;
    (checked ? this.api.verifyHowto(id) : this.api.unverifyHowto(id)).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.changed.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
        this.changed.emit({ ...this.event() });
      },
    });
  }
}
