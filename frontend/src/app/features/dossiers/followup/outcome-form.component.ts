/**
 * "Ergebnis" of the follow-up (M5 contract 3.5): attendance, actual costs, revenue and a note, or the explicit waiver
 * "verzichtet" with a reason. Saves with `PUT /outcome` and `If-Match` on the revision of the dossier; a 409 asks for a
 * reload. The page receives the updated dossier. The guard `outcomeSetOrWaived` is met by attendance and costs (0 counts) or the waiver.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { formatMoney } from '@shared/format.util';
import type { TranslationKey } from '@core/i18n/translations';
import { NoteComponent } from '@shared/ui/note/note.component';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import {
  ButtonComponent,
  CurrencyInputComponent,
  InputComponent,
  SwitchComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { FollowupApi } from '../api/followup-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import {
  type OutcomeErrors,
  type OutcomeFormValue,
  formFromOutcome,
  toOutcomeIn,
} from './outcome-model';

@Component({
  selector: 'app-outcome-form',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    CurrencyInputComponent,
    InputComponent,
    NoteComponent,
    SwitchComponent,
    TextareaComponent,
  ],
  templateUrl: './outcome-form.component.html',
  styleUrl: './outcome-form.component.scss',
})
export class OutcomeFormComponent {
  private readonly api = inject(FollowupApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly changed = output<EventDto>();

  protected readonly form = inject(FormBuilder).nonNullable.group({
    attendance: [''],
    costs: [''],
    revenue: [''],
    notes: [''],
    waived: [false],
    waivedReason: [''],
  });
  protected readonly errors = signal<OutcomeErrors>({});
  protected readonly busy = signal(false);
  protected readonly stale = signal(false);
  protected readonly waived = signal(false);

  /** The stored result as text for the read-only view; `null` before one was entered. */
  protected readonly stored = computed(() => {
    const o = this.event().outcome;
    if (!o) return null;
    const money = (cents: number | null): string =>
      cents === null ? '–' : formatMoney(this.i18n, cents, 'EUR');
    return {
      waived: o.waived,
      reason: o.waivedReason,
      attendance: o.attendance === null ? '–' : String(o.attendance),
      costs: money(o.costsCents),
      revenue: money(o.revenueCents),
      notes: o.notes,
    };
  });

  /** The form starts over only when the stored result changes, not when an unrelated part of the dossier reloads. */
  private readonly storedKey = computed(() => JSON.stringify(this.event().outcome ?? null));

  constructor() {
    effect(() => {
      this.storedKey();
      untracked(() => {
        const value = formFromOutcome(this.event().outcome);
        this.form.reset(value);
        this.waived.set(value.waived);
        this.form.enable();
      });
    });
    this.form.controls.waived.valueChanges.subscribe((w) => this.waived.set(w));
  }

  protected message(field: keyof OutcomeFormValue): string {
    const key: TranslationKey | undefined = this.errors()[field];
    return key ? this.i18n.translate(key) : '';
  }

  protected save(): void {
    if (this.busy()) return;
    const result = toOutcomeIn(this.form.getRawValue());
    if (!result.ok) {
      this.errors.set(result.errors);
      return;
    }
    this.errors.set({});
    this.busy.set(true);
    const e = this.event();
    this.api.putOutcome(e.id, e.rev, result.body).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.stale.set(false);
        this.toast.success(this.i18n.translate('outcome.saved'));
        this.changed.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        if (problem.status === 409 && problem.code === 'conflict') this.stale.set(true);
        else if (problem.code === 'waiver_reason_required')
          this.errors.set({ waivedReason: 'outcome.waiverReason' });
        else this.toast.error(problemMessage(this.i18n, problem));
      },
    });
  }
}
