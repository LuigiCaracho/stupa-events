/**
 * P03 Kalender (`/kalender?month=YYYY-MM&category=`): the public month. The grid (`role="grid"`, arrow keys, "+n") from
 * 769 px on and an agenda by days on a phone come from the shared calendar grid; both read one answer. The month and
 * the category live in the URL. Paging stays within 24 months around today, the range the API accepts.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import {
  CALENDAR_NOW,
  CalendarGridComponent,
} from '@shared/ui/calendar-grid/calendar-grid.component';
import { periodTitle, shiftAnchor, todayKey } from '@shared/ui/calendar-grid/calendar-grid.util';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { anchorOf, gridEntries, monthOf } from '../../model/calendar-entries';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

const MONTH_RANGE = 24;
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

/** Whole months between two `YYYY-MM` keys. */
const monthsBetween = (from: string, to: string): number =>
  (Number(to.slice(0, 4)) - Number(from.slice(0, 4))) * 12 +
  Number(to.slice(5)) -
  Number(from.slice(5));

@Component({
  selector: 'app-calendar-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    CalendarGridComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    NoteComponent,
    SkeletonComponent,
    LinkButtonComponent,
    LoadErrorComponent,
  ],
  templateUrl: './calendar.component.html',
  styleUrl: './calendar.component.scss',
})
export class CalendarPageComponent {
  private readonly api = inject(PublicApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly now = inject(CALENDAR_NOW);

  private readonly queryParams = toSignal(this.route.queryParamMap, {
    initialValue: this.route.snapshot.queryParamMap,
  });
  private readonly thisMonth = monthOf(todayKey(this.now()));
  protected readonly shownMonth = computed(() => {
    const m = this.queryParams().get('month') ?? '';
    return MONTH.test(m) && Math.abs(monthsBetween(this.thisMonth, m)) <= MONTH_RANGE
      ? m
      : this.thisMonth;
  });
  protected readonly shownCategory = computed(() => this.queryParams().get('category') ?? '');
  protected readonly anchor = computed(() => anchorOf(this.shownMonth()));
  protected readonly title = computed(() => periodTitle('month', this.anchor()));

  protected readonly data = rxResource({
    params: () => ({ month: this.shownMonth(), category: this.shownCategory() }),
    stream: ({ params }) => this.api.calendar(params.month, params.category || undefined),
  });
  private readonly categories = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly entries = computed(() =>
    gridEntries(resourceValue(this.data, undefined) ?? null),
  );
  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
  protected readonly empty = computed(
    () => !!resourceValue(this.data, undefined) && this.entries().length === 0,
  );
  protected readonly truncated = computed(
    () => resourceValue(this.data, undefined)?.truncated === true,
  );
  protected readonly canPrev = computed(
    () => monthsBetween(this.thisMonth, this.shownMonth()) > -MONTH_RANGE,
  );
  protected readonly canNext = computed(
    () => monthsBetween(this.thisMonth, this.shownMonth()) < MONTH_RANGE,
  );
  protected readonly isThisMonth = computed(() => this.shownMonth() === this.thisMonth);
  protected readonly options = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('public.calendar.allCategories') },
    ...(resourceValue(this.categories, undefined) ?? []).map((c) => ({
      value: c.slug,
      label: c.name,
    })),
  ]);
  protected readonly subscribeFragment = computed(() =>
    this.shownCategory() ? `k=${this.shownCategory()}` : undefined,
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.calendar.title'));
  }

  protected go(month: string, category = this.shownCategory()): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { month: month === this.thisMonth ? null : month, category: category || null },
    });
  }

  protected today(): void {
    this.go(this.thisMonth);
  }

  protected step(direction: -1 | 1): void {
    this.go(monthOf(shiftAnchor('month', this.anchor(), direction)));
  }

  protected setCategory(slug: string): void {
    this.go(this.shownMonth(), slug);
  }

  protected openDay(anchor: string): void {
    if (monthOf(anchor) !== this.shownMonth()) this.go(monthOf(anchor));
  }

  protected open(slug: string): void {
    void this.router.navigate(['/e', slug]);
  }

  protected reload(): void {
    this.data.reload();
  }
}
