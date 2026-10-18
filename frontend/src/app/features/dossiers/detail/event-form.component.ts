/** Edit form of the dossier core data (title, summary, time, venue, category); emits only the changed fields. */
import { ChangeDetectionStrategy, Component, type OnInit, computed, inject, input, output } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { ButtonComponent, DatepickerComponent, InputComponent, TimeInputComponent } from '@stupa-makers/ui-kit';
import { isoToZoned, zonedToIso } from '../api/event-time';
import type { CategoryRef, EventDto, EventPatch } from '../api/event.models';

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
    TimeInputComponent,
  ],
  templateUrl: './event-form.component.html',
  styleUrl: './event-form.component.scss',
})
export class EventFormComponent implements OnInit {
  readonly event = input.required<EventDto>();
  readonly categories = input<readonly CategoryRef[]>([]);
  readonly busy = input(false);

  readonly save = output<EventPatch>();
  readonly cancelled = output<void>();

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    summary: ['', [Validators.maxLength(200)]],
    venueText: [''],
    primaryCategoryId: [''],
    startDate: ['', [Validators.required]],
    startTime: ['', [Validators.required]],
    endDate: ['', [Validators.required]],
    endTime: ['', [Validators.required]],
  });

  protected readonly categoryOptions = computed<SelectFieldOption[]>(() =>
    this.categories().map((c) => ({ value: c.id, label: c.name })),
  );

  ngOnInit(): void {
    const e = this.event();
    const start = isoToZoned(e.startsAt, e.tzid);
    const end = isoToZoned(e.endsAt, e.tzid);
    this.form.reset({
      title: e.title,
      summary: e.summary ?? '',
      venueText: e.venueText ?? '',
      primaryCategoryId: e.primaryCategory?.id ?? '',
      startDate: start.date,
      startTime: start.time,
      endDate: end.date,
      endTime: end.time,
    });
  }

  private iso(kind: 'start' | 'end'): string {
    const v = this.form.getRawValue();
    return kind === 'start'
      ? zonedToIso(v.startDate, v.startTime, this.event().tzid)
      : zonedToIso(v.endDate, v.endTime, this.event().tzid);
  }

  protected endBeforeStart(): boolean {
    return !this.form.invalid && Date.parse(this.iso('end')) < Date.parse(this.iso('start'));
  }

  protected submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.endBeforeStart()) return;
    const e = this.event();
    const v = this.form.getRawValue();
    const patch: EventPatch = { rev: e.rev };
    if (v.title.trim() !== e.title) patch.title = v.title.trim();
    if (v.summary.trim() !== (e.summary ?? '')) patch.summary = v.summary.trim();
    if (v.venueText.trim() !== (e.venueText ?? '')) patch.venueText = v.venueText.trim();
    if (v.primaryCategoryId && v.primaryCategoryId !== e.primaryCategory?.id) {
      patch.primaryCategoryId = v.primaryCategoryId;
    }
    if (this.iso('start') !== e.startsAt) patch.startsAt = this.iso('start');
    if (this.iso('end') !== e.endsAt) patch.endsAt = this.iso('end');
    this.save.emit(patch);
  }
}
