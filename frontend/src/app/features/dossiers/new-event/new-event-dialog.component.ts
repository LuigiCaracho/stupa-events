/**
 * I05: dialog "Neues Event". Creates a dossier in state `idea` (T00) with title, organization,
 * start and optional end; the organization list is limited to the principal's own organizations.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, output, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { AuthService } from '@core/auth/auth.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import {
  ButtonComponent,
  DatepickerComponent,
  DialogComponent,
  InputComponent,
  TimeInputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { zonedToIso } from '../api/event-time';
import type { CategoryRef, EventCreate, EventDto, OrgRef } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';

const TZID = 'Europe/Berlin';
const DEFAULT_LENGTH_MS = 2 * 60 * 60 * 1000;

@Component({
  selector: 'app-new-event-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslatePipe,
    ButtonComponent,
    DatepickerComponent,
    DialogComponent,
    InputComponent,
    SelectFieldComponent,
    TimeInputComponent,
  ],
  templateUrl: './new-event-dialog.component.html',
  styleUrl: './new-event-dialog.component.scss',
})
export class NewEventDialogComponent {
  private readonly api = inject(EventsApi);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  readonly created = output<EventDto>();
  readonly closed = output<void>();

  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);

  protected readonly lookups = rxResource({
    stream: () =>
      forkJoin({
        orgs: this.api.organizations().pipe(catchError(() => of([] as OrgRef[]))),
        categories: this.api.categories().pipe(catchError(() => of([] as CategoryRef[]))),
      }),
  });

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    organizationId: ['', [Validators.required]],
    primaryCategoryId: [''],
    venueText: [''],
    startDate: ['', [Validators.required]],
    startTime: ['', [Validators.required]],
    endDate: [''],
    endTime: [''],
  });

  protected readonly orgOptions = computed<SelectFieldOption[]>(() => {
    const own = new Set(this.auth.organizations().map((o) => o.slug));
    const global = this.auth.can('event.read_all');
    return (this.lookups.hasValue() ? this.lookups.value().orgs : [])
      .filter((o) => global || own.has(o.slug))
      .map((o) => ({ value: o.id, label: o.name }));
  });

  protected readonly categoryOptions = computed<SelectFieldOption[]>(() =>
    (this.lookups.hasValue() ? this.lookups.value().categories : []).map((c) => ({ value: c.id, label: c.name })),
  );

  constructor() {
    effect(() => {
      const only = this.orgOptions();
      if (only.length === 1 && !this.form.controls.organizationId.value) {
        this.form.controls.organizationId.setValue(only[0].value);
      }
    });
  }

  protected invalid(name: 'title' | 'organizationId' | 'startDate' | 'startTime'): boolean {
    return this.attempted() && this.form.controls[name].invalid;
  }

  private startIso(): string {
    const { startDate, startTime } = this.form.getRawValue();
    return zonedToIso(startDate, startTime, TZID);
  }

  private endIso(): string {
    const { endDate, endTime } = this.form.getRawValue();
    if (!endDate || !endTime) return new Date(Date.parse(this.startIso()) + DEFAULT_LENGTH_MS).toISOString().replace('.000Z', 'Z');
    return zonedToIso(endDate, endTime, TZID);
  }

  protected endBeforeStart(): boolean {
    const { startDate, startTime } = this.form.getRawValue();
    return !!startDate && !!startTime && Date.parse(this.endIso()) < Date.parse(this.startIso());
  }

  protected submit(): void {
    this.attempted.set(true);
    if (this.form.invalid || this.endBeforeStart() || this.busy()) return;
    const v = this.form.getRawValue();
    const body: EventCreate = {
      title: v.title.trim(),
      startsAt: this.startIso(),
      endsAt: this.endIso(),
      tzid: TZID,
      allDay: false,
      organizationId: v.organizationId,
      ...(v.venueText.trim() && { venueText: v.venueText.trim() }),
      ...(v.primaryCategoryId && { primaryCategoryId: v.primaryCategoryId }),
    };
    this.busy.set(true);
    this.api.create(body).subscribe({
      next: (event) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('new.created'));
        this.created.emit(event);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.toast.error(problemMessage(this.i18n, problemOf(err)));
      },
    });
  }
}
