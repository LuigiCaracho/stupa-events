/**
 * P02 Suche (`/suche?q=&category=&organization=&from=&to=&past=`): live search without a button (250 ms after the last
 * key), facet chips with counts, results as rows with a poster thumbnail and "Mehr anzeigen" for the next page. Every
 * filter lives in the URL, so a result list can be shared and the back button restores it. A phone gets one
 * "Filter (n)" button that opens a bottom sheet; a wide screen gets chips and menus.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  linkedSignal,
  signal,
} from '@angular/core';
import { takeUntilDestroyed, rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { resourceValue } from '@core/api/resource-value';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { CALENDAR_NOW } from '@shared/ui/calendar-grid/calendar-grid.component';
import { todayKey } from '@shared/ui/calendar-grid/calendar-grid.util';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SideSheetComponent } from '@shared/ui/side-sheet/side-sheet.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { MEDIA, ButtonComponent, IconComponent } from '@stupa-makers/ui-kit';
import { Subject, catchError, debounceTime, of } from 'rxjs';
import { mediaQuerySignal } from '../../../../layout/media-query';
import { PublicApi } from '../../api/public-api.service';
import { pagedList } from '../../model/paged-list';
import type { PublicEventCard, PublicSearchOut } from '../../model/public.models';
import {
  EMPTY_FILTERS,
  QUERY_MAX_LENGTH,
  type SearchFilters,
  TIME_CHIPS,
  TIME_CHIP_KEYS,
  type TimeChip,
  activeChip,
  activeCount,
  chipRange,
  hasAnyFilter,
  parseFilters,
  toApiQuery,
  toQueryParams,
} from '../../model/search-filters';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

const TYPING_DELAY_MS = 250;
const sameFilters = (a: SearchFilters, b: SearchFilters): boolean =>
  JSON.stringify(a) === JSON.stringify(b);

@Component({
  selector: 'app-search-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    IconComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    SearchPillComponent,
    SideSheetComponent,
    SkeletonComponent,
    EventRowComponent,
    LoadErrorComponent,
  ],
  templateUrl: './search.component.html',
  styleUrl: './search.component.scss',
})
export class SearchComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(PublicApi);
  private readonly i18n = inject(I18nService);
  private readonly today = todayKey(inject(CALENDAR_NOW)());

  protected readonly maxLength = QUERY_MAX_LENGTH;
  protected readonly chips = TIME_CHIPS;
  protected readonly chipKeys = TIME_CHIP_KEYS;
  protected readonly phone = mediaQuerySignal(MEDIA.phone);
  protected readonly sheetOpen = signal(false);
  protected readonly focused = signal(false);

  private readonly params = toSignal(this.route.queryParamMap, {
    initialValue: this.route.snapshot.queryParamMap,
  });
  protected readonly filters = computed(() => parseFilters(this.params()), { equal: sameFilters });
  protected readonly text = linkedSignal(() => this.filters().q);
  private readonly typed = new Subject<string>();

  protected readonly list = pagedList<SearchFilters, PublicEventCard, PublicSearchOut>({
    params: () => this.filters(),
    fetch: (f, cursor) => this.api.events(toApiQuery(f, cursor)),
  });
  private readonly categories = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly facets = linkedSignal<PublicSearchOut | undefined, PublicSearchOut['facets']>({
    source: this.list.first,
    computation: (page, previous) => page?.facets ?? previous?.value ?? null,
  });
  protected readonly total = computed(() => this.list.first()?.total ?? null);
  protected readonly count = computed(() => activeCount(this.filters()));
  protected readonly activeChip = computed(() => activeChip(this.filters(), this.today));
  protected readonly showEmpty = computed(
    () => !!this.list.first() && !this.list.error() && this.list.items().length === 0,
  );
  protected readonly showSkeleton = computed(
    () => this.list.loading() && this.list.items().length === 0,
  );
  protected readonly hasRange = computed(
    () => this.filters().from !== '' || this.filters().to !== '',
  );
  protected readonly suggestions = computed(() =>
    this.focused() && this.text() === '' && this.filters().category.length === 0
      ? (resourceValue(this.categories, undefined) ?? []).filter((c) => c.upcomingCount > 0)
      : [],
  );
  protected readonly categoryOptions = computed<FilterSelectOption[]>(() =>
    (this.facets()?.categories ?? []).map((c) => ({
      value: c.slug,
      label: `${c.name} (${c.count})`,
    })),
  );
  protected readonly organizationOptions = computed<FilterSelectOption[]>(() =>
    (this.facets()?.organizations ?? []).map((o) => ({
      value: o.slug,
      label: `${o.name} (${o.count})`,
    })),
  );
  protected readonly summary = computed(() => {
    const total = this.total();
    if (total === null || this.list.loading()) return '';
    return this.i18n.translate(total === 1 ? 'public.search.countOne' : 'public.search.count', {
      count: total,
    });
  });
  protected readonly emptyHeading = computed(() =>
    this.filters().q.trim()
      ? this.i18n.translate('public.search.emptyQuery', { q: this.filters().q.trim() })
      : this.i18n.translate('public.search.empty'),
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.search.title'));
    this.typed
      .pipe(debounceTime(TYPING_DELAY_MS), takeUntilDestroyed())
      .subscribe(() => this.apply({}, true));
  }

  protected onText(value: string): void {
    this.text.set(value);
    this.typed.next(value);
  }

  protected apply(patch: Partial<SearchFilters>, replace = false): void {
    const next: SearchFilters = { ...this.filters(), q: this.text(), ...patch };
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: toQueryParams(next),
      replaceUrl: replace,
    });
  }

  protected toggleChip(chip: TimeChip): void {
    this.apply(this.activeChip() === chip ? { from: '', to: '' } : chipRange(chip, this.today));
  }

  protected toggleIn(key: 'category' | 'organization', slug: string): void {
    const list = this.filters()[key];
    this.apply({ [key]: list.includes(slug) ? list.filter((s) => s !== slug) : [...list, slug] });
  }

  protected setList(key: 'category' | 'organization', values: readonly string[]): void {
    this.apply({ [key]: values });
  }

  protected widenRange(): void {
    this.apply({ from: '', to: '' });
  }

  protected reset(): void {
    this.apply({ ...EMPTY_FILTERS, q: this.text() });
  }

  protected has(key: 'category' | 'organization', slug: string): boolean {
    return this.filters()[key].includes(slug);
  }

  protected readonly hasAny = computed(() => hasAnyFilter(this.filters()));
}
