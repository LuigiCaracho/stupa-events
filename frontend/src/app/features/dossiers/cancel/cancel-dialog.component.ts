/**
 * The small dialog of the three marks of a published event (M5b contract 7.1): "Absagen", "Verschieben" and "Wieder
 * ansetzen". An internal note (optional, never public), the public reason from a fixed list with a short public text,
 * for a postponement the new date (or "neuer Termin folgt") and a preview of what the public status will say.
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
  ToastService,
} from '@stupa-makers/ui-kit';
import type { Observable } from 'rxjs';
import type { CancelBody, PostponeBody } from '../api/action.models';
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

const TITLE = {
  cancel: 'cancel.titleCancel',
  postpone: 'cancel.titlePostpone',
  reinstate: 'cancel.titleReinstate',
} as const;

const SUBMIT = {
  cancel: 'cancel.submitCancel',
  postpone: 'cancel.submitPostpone',
  reinstate: 'cancel.submitReinstate',
} as const;

const DONE = {
  cancel: 'cancel.doneCancel',
  postpone: 'cancel.donePostpone',
  reinstate: 'cancel.doneReinstate',
} as const;

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
  readonly mode = input.required<CancelMode>();
  readonly done = output<EventDto>();
  readonly stale = output<void>();
  readonly closed = output<void>();

  protected readonly reason = signal('');
  protected readonly code = signal<PublicReasonCode>('none');
  protected readonly publicText = signal('');
  protected readonly newDate = signal('');
  protected readonly newTime = signal('');
  protected readonly busy = signal(false);

  protected readonly textMax = PUBLIC_TEXT_MAX;
  protected readonly TITLE = TITLE;
  protected readonly SUBMIT = SUBMIT;

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
      this.mode() === 'postpone' ? 'publicStatus.postponed' : 'publicStatus.cancelled',
    );
    const why = this.i18n.translate(`publicReason.${this.code()}`);
    return this.code() === 'none' ? status : `${status} · ${why}`;
  });

  private call(e: EventDto, body: ReturnType<typeof cancelBody>): Observable<EventDto> {
    switch (this.mode()) {
      case 'cancel':
        return this.api.cancel(e.id, e.rev, body as CancelBody);
      case 'postpone':
        return this.api.postpone(e.id, e.rev, body as PostponeBody);
      case 'reinstate':
        return this.api.reinstate(e.id, e.rev, body);
    }
  }

  protected submit(): void {
    if (this.error() || this.busy()) return;
    this.busy.set(true);
    const e = this.event();
    const body = cancelBody(this.form());
    this.call(e, body).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate(DONE[this.mode()]));
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
