/**
 * I14: cancel or postpone a live event. An internal reason (required, never public), a public reason from a fixed list
 * with a short public text (editorial approval only), for a postponement the new date (only with the right to change
 * critical fields) or "neuer Termin folgt", and a preview of what the public status will say.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { DatetimeFieldComponent } from '@shared/ui/datetime-field/datetime-field.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import {
  ButtonComponent,
  DialogComponent,
  InputComponent,
  SegmentedComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import type { EventDto, PublicReasonCode } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import {
  type CancelError,
  type CancelMode,
  PUBLIC_REASON_CODES,
  PUBLIC_TEXT_MAX,
  cancelBody,
  cancelError,
} from './cancel-request';

@Component({
  selector: 'app-cancel-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    DatetimeFieldComponent,
    DialogComponent,
    InputComponent,
    NoteComponent,
    SegmentedComponent,
    SelectFieldComponent,
  ],
  templateUrl: './cancel-dialog.component.html',
  styleUrl: './cancel-dialog.component.scss',
})
export class CancelDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly done = output<EventDto>();
  readonly stale = output<void>();
  readonly closed = output<void>();

  protected readonly mode = signal<CancelMode>('cancel');
  protected readonly reason = signal('');
  protected readonly code = signal<PublicReasonCode>('none');
  protected readonly publicText = signal('');
  protected readonly newDate = signal('');
  protected readonly newTime = signal('');
  protected readonly attempted = signal(false);
  protected readonly busy = signal(false);

  protected readonly mayWriteText = computed(() =>
    (this.event().allowedActions ?? []).includes('public-text'),
  );
  protected readonly mayMove = computed(() =>
    (this.event().allowedActions ?? []).includes('postpone-with-date'),
  );
  protected readonly textMax = PUBLIC_TEXT_MAX;

  protected readonly modeOptions = computed(() =>
    (['cancel', 'postpone'] as const).map((value) => ({
      value,
      label: this.i18n.translate(`cancel.mode.${value}`),
    })),
  );
  protected readonly codeOptions = computed<SelectFieldOption[]>(() =>
    PUBLIC_REASON_CODES.map((value) => ({
      value,
      label: this.i18n.translate(`publicReason.${value}`),
    })),
  );

  private readonly form = computed(() => ({
    mode: this.mode(),
    reason: this.reason(),
    code: this.code(),
    publicText: this.publicText(),
    newDate: this.newDate(),
    newTime: this.newTime(),
    tzid: this.event().tzid,
    now: new Date(),
  }));
  protected readonly error = computed<CancelError>(() => cancelError(this.form()));

  protected readonly preview = computed(() => {
    const status = this.i18n.translate(
      this.mode() === 'cancel' ? 'publicStatus.cancelled' : 'publicStatus.postponed',
    );
    const why = this.i18n.translate(`publicReason.${this.code()}`);
    return this.code() === 'none' ? status : `${status} · ${why}`;
  });

  protected submit(): void {
    this.attempted.set(true);
    if (this.error() || this.busy()) return;
    this.busy.set(true);
    const e = this.event();
    const body = cancelBody(this.form(), this.mayWriteText());
    this.api.action(e.id, this.mode(), body, e.rev).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(
          this.i18n.translate(
            this.mode() === 'cancel' ? 'cancel.doneCancel' : 'cancel.donePostpone',
          ),
        );
        this.done.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        this.toast.error(problemMessage(this.i18n, problem));
        if (problem.status === 409) this.stale.emit();
      },
    });
  }
}
