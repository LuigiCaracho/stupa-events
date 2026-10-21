/**
 * The dossier form (I07). Every field the server does not list in `editableFields` is locked; an archived dossier says
 * why. The form reports its complete set of changes against the event on every keystroke; the page feeds that to the
 * autosave and sends it on "Speichern". Time, place and links form one group, the texts another.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  input,
  output,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { TextareaComponent } from '@shared/ui/textarea/textarea.component';
import {
  ButtonComponent,
  DatepickerComponent,
  InputComponent,
  TimeInputComponent,
} from '@stupa-makers/ui-kit';
import { categoryOptions as treeOptions } from '../api/category-options';
import type { CategoryRef, EventDto, EventFields, VenueRef } from '../api/event.models';
import {
  CONTROL_FIELD,
  type FormValue,
  badLink,
  diff,
  editableFields,
  endBeforeStart,
  valueOf,
} from './form-model';

@Component({
  selector: 'app-event-form',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    DatepickerComponent,
    InputComponent,
    SelectFieldComponent,
    TextareaComponent,
    TimeInputComponent,
  ],
  templateUrl: './event-form.component.html',
  styleUrl: './event-form.component.scss',
})
export class EventFormComponent {
  readonly event = input.required<EventDto>();
  readonly categories = input<readonly CategoryRef[]>([]);
  readonly venues = input<readonly VenueRef[]>([]);
  /** Changes restored from a draft; they are laid over the event once. */
  readonly draft = input<EventFields | null>(null);
  readonly busy = input(false);

  readonly changes = output<EventFields>();
  readonly saveClicked = output<void>();

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    summary: ['', [Validators.maxLength(200)]],
    descriptionMd: [''],
    costText: ['', [Validators.maxLength(200)]],
    startDate: ['', [Validators.required]],
    startTime: ['', [Validators.required]],
    endDate: ['', [Validators.required]],
    endTime: ['', [Validators.required]],
    venueId: [''],
    venueText: [''],
    primaryCategoryId: [''],
    ticketUrl: [''],
    websiteUrl: [''],
  });

  protected readonly categoryOptions = computed<SelectFieldOption[]>(() =>
    treeOptions(this.categories()),
  );
  protected readonly venueOptions = computed<SelectFieldOption[]>(() =>
    this.venues().map((v) => ({ value: v.id, label: v.name })),
  );
  protected readonly editable = computed(() => new Set(editableFields(this.event())));
  protected readonly lockKey = computed<TranslationKey | null>(() =>
    this.event().state === 'archived' ? 'lock.archived' : null,
  );
  protected readonly anyEditable = computed(() => this.editable().size > 0);

  constructor() {
    effect(() => {
      const event = this.event();
      const draft = this.draft();
      untracked(() => {
        this.form.reset(valueOf(event, draft ?? {}), { emitEvent: false });
        this.applyLocks();
        if (draft) this.emit();
      });
    });
    this.form.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.emit());
  }

  private applyLocks(): void {
    const editable = this.editable();
    for (const [name, control] of Object.entries(this.form.controls)) {
      const field = CONTROL_FIELD[name as keyof FormValue];
      if (editable.has(field)) control.enable({ emitEvent: false });
      else control.disable({ emitEvent: false });
    }
  }

  private emit(): void {
    this.changes.emit(diff(this.event(), this.form.getRawValue()));
  }

  protected locked(name: keyof FormValue): boolean {
    return this.form.controls[name].disabled;
  }

  protected hint(name: keyof FormValue): TranslationKey | null {
    return this.locked(name) ? this.lockKey() : null;
  }

  protected linkError(name: 'ticketUrl' | 'websiteUrl'): boolean {
    return badLink(this.form.controls[name].value);
  }

  protected endError(): boolean {
    return endBeforeStart(this.form.getRawValue(), this.event().tzid);
  }

  protected submit(): void {
    this.form.markAllAsTouched();
    const value = this.form.getRawValue();
    if (
      this.form.invalid ||
      this.endError() ||
      badLink(value.ticketUrl) ||
      badLink(value.websiteUrl)
    )
      return;
    this.saveClicked.emit();
  }
}
