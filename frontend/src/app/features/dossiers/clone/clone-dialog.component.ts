/**
 * I06: "Neu aus Vorlage" (dialog over the dossier list, `/dossiers/neu?vorlage=<id>`). A live search over the
 * templates (`GET /api/templates`) with the filters format, category and year, the hits grouped by format with the review
 * state of their howto, and for the chosen one the preview "Was wird übernommen", "Letztes Mal" and, for an own
 * template, "Angebote der letzten Auflage". The form takes organization (when there is a choice), the new start, an
 * optional end and title; for an all-day template the times are left out (only the days count). On a phone the dialog has two steps: the list, then preview and form.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { rxResource, takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { mediaQuerySignal } from '../../../layout/media-query';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { QuoteTableComponent } from '@shared/ui/quote-table/quote-table.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SelectFieldComponent, type SelectFieldOption } from '@shared/ui/select/select.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import {
  ButtonComponent,
  DatepickerComponent,
  DialogComponent,
  InputComponent,
  MEDIA,
  SegmentedComponent,
  TimeInputComponent,
  ToastService,
} from '@stupa-makers/ui-kit';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { LastTimeCardComponent } from '../../archive/last-time/last-time-card.component';
import type {
  CloneIn,
  ClonePreview,
  TemplateCard,
  TemplatePage,
} from '../../archive/model/archive.models';
import { resourceValue } from '@core/api/resource-value';
import { CarryOverListComponent } from '../../archive/preview/carry-over-list.component';
import { FormatsApi } from '../../formats/api/formats-api.service';
import type { FormatPage } from '../../formats/model/format.models';
import { AttachmentsApi } from '../api/attachments-api.service';
import { zonedToIso } from '../api/event-time';
import type { CategoryRef, OrgRef } from '../api/event.models';
import type { QuoteGroup } from '../model/attachment.models';
import { EventsApi } from '../api/events-api.service';
import { problemMessage } from '../api/problem-message';
import { groupByFormat } from './template-groups';

const TZID = 'Europe/Berlin';
const NOON = '12:00';

const slugOptions = (nodes: readonly CategoryRef[], depth = 0): FilterSelectOption[] =>
  nodes.flatMap((c) => [
    { value: c.slug, label: `${'\u2003'.repeat(depth)}${c.name}` },
    ...slugOptions(c.children ?? [], depth + 1),
  ]);
const SEARCH_DELAY_MS = 250;
const EMPTY_TEMPLATES: TemplatePage = { items: [], total: 0, limit: 50, offset: 0 };
const EMPTY_PREVIEW: ClonePreview = { report: [], lastTime: null };
const EMPTY_FORMATS: FormatPage = { items: [], total: 0, limit: 100, offset: 0 };

@Component({
  selector: 'app-clone-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    LocalizedDatePipe,
    TranslatePipe,
    ButtonComponent,
    CarryOverListComponent,
    DatepickerComponent,
    DialogComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    InputComponent,
    LastTimeCardComponent,
    ListItemComponent,
    NoteComponent,
    QuoteTableComponent,
    SearchPillComponent,
    SegmentedComponent,
    SelectFieldComponent,
    SkeletonComponent,
    StatusTextComponent,
    TimeInputComponent,
  ],
  templateUrl: './clone-dialog.component.html',
  styleUrl: './clone-dialog.component.scss',
})
export class CloneDialogComponent {
  private readonly archive = inject(ArchiveApi);
  private readonly events = inject(EventsApi);
  private readonly formats = inject(FormatsApi);
  private readonly attachments = inject(AttachmentsApi);
  private readonly toast = inject(ToastService);
  private readonly i18n = inject(I18nService);

  /** The template chosen from the start (`?vorlage=`), if any. */
  readonly templateId = input<string | null>(null);
  /** A format the list starts filtered by ("Neue Ausgabe" on the format page). */
  readonly formatSlug = input<string | null>(null);

  readonly closed = output<void>();
  readonly created = output<string>();
  readonly switchToBlank = output<void>();

  protected readonly phone = mediaQuerySignal(MEDIA.phone);
  protected readonly step = signal<'pick' | 'preview'>('pick');
  protected readonly q = signal('');
  protected readonly applied = signal({ q: '', format: '', category: '', year: '' });
  protected readonly busy = signal(false);
  protected readonly attempted = signal(false);
  protected readonly selectedId = signal<string | null>(null);
  protected readonly organizationId = signal('');
  private timer: ReturnType<typeof setTimeout> | undefined;

  protected readonly lookups = rxResource({
    stream: () =>
      forkJoin({
        orgs: this.events.organizations().pipe(catchError(() => of([] as OrgRef[]))),
        categories: this.events.categories().pipe(catchError(() => of([] as CategoryRef[]))),
        formats: this.formats.list({ limit: 100 }).pipe(catchError(() => of(EMPTY_FORMATS))),
      }),
  });
  private readonly lookup = computed(() =>
    resourceValue(this.lookups, { orgs: [], categories: [], formats: EMPTY_FORMATS }),
  );
  protected readonly templates = rxResource({
    params: () => this.applied(),
    stream: ({ params }) =>
      this.archive.templates({
        q: params.q || undefined,
        format: params.format || undefined,
        category: params.category || undefined,
        year: params.year || undefined,
        limit: 50,
      }),
  });
  protected readonly preview = rxResource({
    params: () => {
      const id = this.selectedId();
      return id ? { id, org: this.organizationId() } : undefined;
    },
    stream: ({ params }) => this.archive.clonePreview(params.id, params.org || undefined),
  });
  protected readonly quotes = rxResource({
    params: () => {
      const t = this.selected();
      return t && !t.foreign ? t.id : undefined;
    },
    stream: ({ params }) =>
      this.attachments.quotes(params).pipe(
        map((q) => q.groups.filter((g) => g.quotes.length > 0)),
        catchError(() => of([] as QuoteGroup[])),
      ),
  });

  protected readonly groups = computed(() =>
    groupByFormat(resourceValue(this.templates, EMPTY_TEMPLATES).items),
  );
  protected readonly selected = computed<TemplateCard | null>(() => {
    const id = this.selectedId();
    const items = resourceValue(this.templates, EMPTY_TEMPLATES).items;
    return items.find((t) => t.id === id) ?? null;
  });
  protected readonly allDay = computed(() => this.selected()?.allDay === true);
  protected readonly lastTime = computed(() => resourceValue(this.preview, EMPTY_PREVIEW).lastTime);
  protected readonly quoteGroups = computed(() => resourceValue(this.quotes, [] as QuoteGroup[]));

  /** The server lists only the organizations the person may create events in (`creatable=true`). */
  protected readonly orgOptions = computed<SelectFieldOption[]>(() =>
    this.lookup().orgs.map((o) => ({ value: o.id, label: o.name })),
  );
  protected readonly formatOptions = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('search.allFormats') },
    ...this.lookup().formats.items.map((f) => ({
      value: f.slug,
      label: f.title,
    })),
  ]);
  protected readonly categoryOptions = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('filters.allCategories') },
    ...slugOptions(this.lookup().categories),
  ]);
  protected readonly yearOptions = computed<FilterSelectOption[]>(() => {
    const now = new Date().getFullYear();
    return [
      { value: '', label: this.i18n.translate('search.allYears') },
      ...Array.from({ length: 6 }, (_, i) => String(now - i)).map((y) => ({ value: y, label: y })),
    ];
  });

  protected readonly form = inject(FormBuilder).nonNullable.group({
    organizationId: [''],
    title: ['', [Validators.maxLength(200)]],
    startDate: ['', [Validators.required]],
    startTime: ['', [Validators.required]],
    endDate: [''],
    endTime: [''],
  });

  protected readonly showList = computed(() => !this.phone() || this.step() === 'pick');
  protected readonly showPreview = computed(
    () => this.selectedId() !== null && (!this.phone() || this.step() === 'preview'),
  );

  constructor() {
    effect(() => {
      const id = this.templateId();
      untracked(() => {
        if (!id) return;
        this.selectedId.set(id);
        this.step.set('preview');
      });
    });
    effect(() => {
      const slug = this.formatSlug();
      untracked(() => {
        if (slug) this.applied.update((a) => ({ ...a, format: slug }));
      });
    });
    effect(() => {
      const allDay = this.allDay();
      untracked(() => {
        const time = this.form.controls.startTime;
        time.setValidators(allDay ? [] : [Validators.required]);
        time.updateValueAndValidity();
      });
    });
    effect(() => {
      const options = this.orgOptions();
      const t = this.selected();
      untracked(() => {
        if (this.form.controls.organizationId.value || options.length === 0) return;
        const same = options.find((o) => o.label === t?.organization.name);
        this.form.controls.organizationId.setValue((same ?? options[0]).value);
      });
    });
    this.form.controls.organizationId.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe((v) => this.organizationId.set(v));
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }

  protected typing(value: string): void {
    this.q.set(value);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.applied.update((a) => ({ ...a, q: value.trim() })), SEARCH_DELAY_MS);
  }

  protected filter(key: 'format' | 'category' | 'year', value: string): void {
    this.applied.update((a) => ({ ...a, [key]: value }));
  }

  protected pick(card: TemplateCard): void {
    this.selectedId.set(card.id);
    this.step.set('preview');
  }

  protected backToList(): void {
    this.step.set('pick');
  }

  protected sub(card: TemplateCard): string {
    const people =
      card.attendance === null
        ? []
        : [this.i18n.translate('clone.attendance', { count: card.attendance })];
    return [card.organization.short, ...people].join(' · ');
  }

  protected invalidStart(): boolean {
    return this.attempted() && (this.form.controls.startDate.invalid || this.form.controls.startTime.invalid);
  }

  private endIso(): string | undefined {
    const { endDate, endTime } = this.form.getRawValue();
    const time = this.allDay() ? NOON : endTime;
    return endDate && time ? zonedToIso(endDate, time, TZID) : undefined;
  }

  private startTime(): string {
    return this.allDay() ? NOON : this.form.getRawValue().startTime;
  }

  protected endBeforeStart(): boolean {
    const { startDate } = this.form.getRawValue();
    const start = this.startTime();
    const end = this.endIso();
    return (
      !!end &&
      !!startDate &&
      !!start &&
      Date.parse(end) < Date.parse(zonedToIso(startDate, start, TZID))
    );
  }

  protected submit(): void {
    this.attempted.set(true);
    const id = this.selectedId();
    const v = this.form.getRawValue();
    if (!id || this.form.invalid || this.endBeforeStart() || this.busy()) return;
    const endsAt = this.endIso();
    const body: CloneIn = {
      startsAt: zonedToIso(v.startDate, this.startTime(), TZID),
      ...(endsAt && { endsAt }),
      ...(this.orgOptions().length > 1 && v.organizationId && { organizationId: v.organizationId }),
      ...(v.title.trim() && { title: v.title.trim() }),
    };
    this.busy.set(true);
    this.archive.clone(id, body).subscribe({
      next: (out) => {
        this.busy.set(false);
        this.toast.success(this.i18n.translate('clone.created'));
        this.created.emit(out.event.id);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        const problem = problemOf(err);
        if (problem.status === 404 || problem.code === 'not_a_template') {
          this.toast.error(this.i18n.translate('clone.gone'));
          this.templates.reload();
        } else if (problem.code === 'organization_required') {
          this.toast.error(this.i18n.translate('clone.orgRequired'));
        } else {
          this.toast.error(problemMessage(this.i18n, problem));
        }
      },
    });
  }
}
