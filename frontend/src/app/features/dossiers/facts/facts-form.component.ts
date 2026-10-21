/**
 * "Rahmen" (M5 contract 3.6, 11.5): the facts block of the overview, with the fields of the profile of the main
 * category (generic, party, meeting, trip). A party without an age limit gets the hint `facts_incomplete`. Saves with `PUT /facts` and `If-Match`;
 * the page receives the updated dossier. Read only when the state locks it.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import { SelectFieldComponent } from '@shared/ui/select/select.component';
import { ButtonComponent, CheckboxComponent, CurrencyInputComponent, InputComponent, ToastService } from '@stupa-makers/ui-kit';
import { OutcomeApi } from '../api/outcome-api.service';
import type { EventDto } from '../api/event.models';
import { problemMessage } from '../api/problem-message';
import { type FactKind, type FactsFormValue, fieldsOf, formFromFacts, toFacts } from './facts-profiles';
import type { TranslationKey } from '@core/i18n/translations';

@Component({
  selector: 'app-facts-form',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    FormsModule,
    TranslatePipe,
    ButtonComponent,
    CheckboxComponent,
    CurrencyInputComponent,
    InputComponent,
    SelectFieldComponent,
    TextareaComponent,
  ],
  templateUrl: './facts-form.component.html',
  styleUrl: './facts-form.component.scss',
})
export class FactsFormComponent {
  private readonly api = inject(OutcomeApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly event = input.required<EventDto>();
  readonly canEdit = input(false);
  readonly changed = output<EventDto>();

  protected readonly fields = computed(() => fieldsOf(this.event().primaryCategory?.requiredProfile));
  protected readonly value = signal<FactsFormValue>({});
  protected readonly errors = signal<Record<string, TranslationKey>>({});
  protected readonly busy = signal(false);
  protected readonly ageOptions = [
    { value: '0', label: this.i18n.translate('facts.age.0') },
    { value: '16', label: this.i18n.translate('facts.age.16') },
    { value: '18', label: this.i18n.translate('facts.age.18') },
  ];

  /** The form starts over only when the stored facts or the profile change. */
  private readonly storedKey = computed(
    () => `${this.event().primaryCategory?.requiredProfile}:${JSON.stringify(this.event().facts ?? null)}`,
  );

  constructor() {
    effect(() => {
      this.storedKey();
      untracked(() => {
        const e = this.event();
        this.value.set(formFromFacts(e.primaryCategory?.requiredProfile, e.facts));
        this.errors.set({});
      });
    });
  }

  /** The filled fields as label and text, for the read-only view. */
  protected readonly summary = computed(() =>
    this.fields()
      .map((f) => ({ label: f.label, text: this.shown(f.kind, this.value()[f.key]) }))
      .filter((row) => row.text !== ''),
  );

  private shown(kind: FactKind, v: string | boolean): string {
    if (v === true) return this.i18n.translate('facts.yes');
    if (typeof v !== 'string' || v === '') return '';
    if (kind === 'age') return this.i18n.translate(`facts.age.${v}` as TranslationKey);
    return kind === 'cents' ? `${v.replace('.', ',')} €` : v;
  }

  protected text(key: string): string {
    return this.value()[key] as string;
  }

  protected ticked(key: string): boolean {
    return this.value()[key] === true;
  }

  protected set(key: string, v: string | boolean): void {
    this.value.update((cur) => ({ ...cur, [key]: v }));
  }

  protected error(key: string): string {
    const k = this.errors()[key];
    return k ? this.i18n.translate(k) : '';
  }

  protected save(): void {
    if (this.busy()) return;
    const e = this.event();
    const result = toFacts(e.primaryCategory?.requiredProfile, this.value());
    if (!result.ok) {
      this.errors.set(result.errors);
      return;
    }
    this.errors.set({});
    this.busy.set(true);
    this.api.putFacts(e.id, e.rev, result.facts).subscribe({
      next: (updated) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('facts.saved'));
        this.changed.emit(updated);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
