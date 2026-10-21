/**
 * The filter row of the board (I03) and the dossier list (I04): search, organization, category, period,
 * "Nur meine" and, on the board, the view Aktiv | Archiv | Verworfen. The page owns the value; this component
 * only emits the next one.
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
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import type { CategoryRef, OrgRef } from '../../dossiers/api/event.models';
import { EventsApi } from '../../dossiers/api/events-api.service';
import {
  type BoardView,
  NO_FILTERS,
  type PipelineFilters,
  type RangePreset,
  activeFilterCount,
} from './pipeline-filters';

const RANGE_OPTIONS: readonly RangePreset[] = ['', 'week', 'month', 'next30', 'past'];

const flatten = (nodes: readonly CategoryRef[]): CategoryRef[] =>
  nodes.flatMap((c) => [c, ...flatten(c.children ?? [])]);

@Component({
  selector: 'app-pipeline-filters',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    FilterSelectComponent,
    SearchPillComponent,
    SegmentedComponent,
  ],
  templateUrl: './pipeline-filters.component.html',
  styleUrl: './pipeline-filters.component.scss',
})
export class PipelineFiltersComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);

  readonly filters = input.required<PipelineFilters>();
  readonly showView = input(false);
  /** The calendar chooses its own period. */
  readonly showPeriod = input(true);
  readonly changed = output<PipelineFilters>();

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

  protected readonly rangeOptions = computed<FilterSelectOption[]>(() =>
    RANGE_OPTIONS.map((r) => ({
      value: r,
      label: this.i18n.translate(`filters.range.${r || 'all'}`),
    })),
  );

  protected readonly viewOptions = computed<SegmentedOption[]>(() =>
    (['active', 'archived', 'withdrawn'] as const).map((v) => ({
      value: v,
      label: this.i18n.translate(`filters.view.${v}`),
    })),
  );

  protected readonly count = computed(() => activeFilterCount(this.filters()));

  protected set<K extends keyof PipelineFilters>(key: K, value: PipelineFilters[K]): void {
    this.changed.emit({ ...this.filters(), [key]: value });
  }

  protected setView(value: string | null): void {
    this.set('view', (value ?? 'active') as BoardView);
  }

  protected reset(): void {
    this.changed.emit({ ...NO_FILTERS, view: this.filters().view });
  }
}
