/**
 * The filter row of the event list and its calendar (M5b contract 10.2): search, chips for organization, category,
 * state and year, "Nur meine" and the reset button. The page owns the value; this component only emits the next one.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import type { CategoryRef, OrgRef } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import {
  type EventFilters,
  NO_FILTERS,
  STATE_CHIPS,
  type StateChip,
  activeFilterCount,
} from './event-filters';

const YEARS_BACK = 3;
const YEARS_AHEAD = 1;

const flatten = (nodes: readonly CategoryRef[]): CategoryRef[] =>
  nodes.flatMap((c) => [c, ...flatten(c.children ?? [])]);

@Component({
  selector: 'app-event-filters',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, ButtonComponent, FilterSelectComponent, SearchPillComponent],
  templateUrl: './event-filters.component.html',
  styleUrl: './event-filters.component.scss',
})
export class EventFiltersComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);

  readonly filters = input.required<EventFilters>();
  /** The year the "Jahr" chip counts back from; the page passes today. */
  readonly today = input(new Date());
  readonly changed = output<EventFilters>();

  protected readonly lookups = rxResource({
    stream: () =>
      forkJoin({
        orgs: this.api.allOrganizations().pipe(catchError(() => of([] as OrgRef[]))),
        categories: this.api.categories().pipe(catchError(() => of([] as CategoryRef[]))),
      }),
  });

  protected readonly orgOptions = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('filters.allOrgs') },
    ...(this.lookups.hasValue() ? this.lookups.value().orgs : []).map((o) => ({
      value: o.slug,
      label: o.short,
    })),
  ]);

  protected readonly categoryOptions = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('filters.allCategories') },
    ...flatten(this.lookups.hasValue() ? this.lookups.value().categories : []).map((c) => ({
      value: c.slug,
      label: c.name,
    })),
  ]);

  protected readonly stateOptions = computed<FilterSelectOption[]>(() => [
    { value: '', label: this.i18n.translate('filters.allStates') },
    ...STATE_CHIPS.map((s) => ({ value: s, label: this.i18n.translate(`filters.state.${s}`) })),
  ]);

  protected readonly yearOptions = computed<FilterSelectOption[]>(() => {
    const now = this.today().getFullYear();
    const years = Array.from({ length: YEARS_BACK + YEARS_AHEAD + 1 }, (_, i) =>
      String(now + YEARS_AHEAD - i),
    );
    return [
      { value: '', label: this.i18n.translate('filters.allYears') },
      ...years.map((y) => ({ value: y, label: y })),
    ];
  });

  protected readonly count = computed(() => activeFilterCount(this.filters()));

  protected set<K extends keyof EventFilters>(key: K, value: EventFilters[K]): void {
    this.changed.emit({ ...this.filters(), [key]: value });
  }

  protected setState(value: string): void {
    this.set('state', value as StateChip);
  }

  protected reset(): void {
    this.changed.emit({ ...NO_FILTERS, view: this.filters().view });
  }
}
