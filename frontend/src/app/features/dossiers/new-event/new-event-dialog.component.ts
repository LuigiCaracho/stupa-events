/**
 * I05: dialog "Neues Event" or "Vorschlag". Creates a dossier in state `idea` (T00) with title, organization,
 * start and optional end (the server adds two hours). A person without an organization of their own makes a proposal:
 * the organization field is fixed and locked, the editorial staff assigns one later; five open proposals at most.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  output,
  signal,
} from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
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
  SegmentedComponent,
  TimeInputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { zonedToIso } from '../api/event-time';
import type { CategoryRef, EventCreate, EventDto, OrgRef } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { categoryOptions as treeOptions } from '../api/category-options';
import { problemMessage } from '../api/problem-message';

const TZID = 'Europe/Berlin';

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
    SegmentedComponent,
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
  readonly switchToTemplate = output<void>();

  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);

  protected readonly lookups = rxResource({
    stream: () =>
      forkJoin({
        orgs: this.api.organizations().pipe(catchError(() => of([] as OrgRef[]))),
        categories: this.api.categories().pipe(catchError(() => of([] as CategoryRef[]))),
      }),
  });

  protected readonly proposalOrg = new FormControl({
    value: this.i18n.translate('new.proposalOrg'),
    disabled: true,
  });

  protected readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    organizationId: [''],
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

  /** No organization to choose from: the dossier is a proposal. */
  protected readonly proposal = computed(
    () => !this.lookups.isLoading() && this.orgOptions().length === 0,
  );

  protected readonly categoryOptions = computed<SelectFieldOption[]>(() =>
    treeOptions(this.lookups.hasValue() ? this.lookups.value().categories : []),
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
    if (name === 'organizationId')
      return this.attempted() && !this.proposal() && !this.form.controls[name].value;
    return this.attempted() && this.form.controls[name].invalid;
  }

  private startIso(): string {
    const { startDate, startTime } = this.form.getRawValue();
    return zonedToIso(startDate, startTime, TZID);
  }

  private endIso(): string | undefined {
    const { endDate, endTime } = this.form.getRawValue();
    return endDate && endTime ? zonedToIso(endDate, endTime, TZID) : undefined;
  }

  protected endBeforeStart(): boolean {
    const { startDate, startTime } = this.form.getRawValue();
    const end = this.endIso();
    return !!startDate && !!startTime && !!end && Date.parse(end) < Date.parse(this.startIso());
  }

  protected submit(): void {
    this.attempted.set(true);
    const v = this.form.getRawValue();
    if (this.form.invalid || this.endBeforeStart() || this.busy()) return;
    if (!this.proposal() && !v.organizationId) return;
    const endsAt = this.endIso();
    const body: EventCreate = {
      title: v.title.trim(),
      startsAt: this.startIso(),
      ...(endsAt && { endsAt }),
      tzid: TZID,
      allDay: false,
      ...(!this.proposal() && { organizationId: v.organizationId }),
      ...(v.venueText.trim() && { venueText: v.venueText.trim() }),
      ...(v.primaryCategoryId && { primaryCategoryId: v.primaryCategoryId }),
    };
    this.busy.set(true);
    this.api.create(body).subscribe({
      next: (event) => {
        this.busy.set(false);
        this.toast.success(
          this.i18n.translate(this.proposal() ? 'new.createdProposal' : 'new.created'),
        );
        this.created.emit(event);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        this.toast.error(
          problem.status === 404 && !this.proposal()
            ? this.i18n.translate('new.errOrgScope')
            : problemMessage(this.i18n, problem),
        );
      },
    });
  }
}
