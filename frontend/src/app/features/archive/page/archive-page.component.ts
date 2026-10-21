/**
 * I20: archive and search (`/archiv`). A live search field (250 ms), the switch Dossiers | Dokumente | Formate, facets
 * with counts as filter chips, hits with highlighted words and the review date of the howto. Without a search term
 * the page only hints; a term that finds nothing offers the "did you mean" suggestion of the server. The filters live
 * in the URL (`q, scope, status, org, jahr, kategorie, format`), the default state filter is `archived`.
 */
import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { problemOf } from '@core/api/problem';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { createUrlState } from '@shared/url-state';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { ArchiveApi } from '../api/archive-api.service';
import { SearchHitComponent } from '../hit/search-hit.component';
import type { Facet, SearchHit, SearchOut, SearchScope } from '../model/archive.models';
import {
  type ArchiveFilters,
  MAX_QUERY,
  activeFacets,
  archiveFromParams,
  archiveToParams,
  archiveToQuery,
  searchable,
} from './archive-filters';
import { resourceValue } from '@core/api/resource-value';

const SCOPES: readonly SearchScope[] = ['events', 'documents', 'formats'];
const EMPTY: SearchOut = {
  q: '',
  scope: 'events',
  total: 0,
  hits: [],
  facets: { state: [], organization: [], year: [], category: [], format: [] },
  suggestion: null,
};

@Component({
  selector: 'app-archive-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    NoteComponent,
    PageHeaderComponent,
    SearchHitComponent,
    SearchPillComponent,
    SegmentedComponent,
    SkeletonComponent,
    StickyBarComponent,
  ],
  templateUrl: './archive-page.component.html',
  styleUrl: './archive-page.component.scss',
})
export class ArchivePageComponent {
  private readonly api = inject(ArchiveApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);

  protected readonly maxQuery = MAX_QUERY;
  protected readonly state = createUrlState<ArchiveFilters>({
    parse: archiveFromParams,
    serialize: archiveToParams,
    typing: (a, b) => a.q !== b.q,
  });

  protected readonly result = rxResource({
    params: () => (searchable(this.state.applied()) ? this.state.applied() : undefined),
    stream: ({ params }) => this.api.search(archiveToQuery(params)),
  });
  private readonly more = signal<SearchHit[]>([]);
  protected readonly loadingMore = signal(false);

  protected readonly hits = computed(() => [
    ...resourceValue(this.result, EMPTY).hits,
    ...this.more(),
  ]);
  protected readonly total = computed(() => resourceValue(this.result, EMPTY).total);
  protected readonly facets = computed(() => resourceValue(this.result, EMPTY).facets);
  protected readonly suggestion = computed(() => resourceValue(this.result, EMPTY).suggestion);
  protected readonly canMore = computed(() => this.hits().length < this.total());
  protected readonly started = computed(() => searchable(this.state.applied()));
  protected readonly facetCount = computed(() => activeFacets(this.state.value()));
  protected readonly errorKey = computed<TranslationKey | null>(() => {
    const error = this.result.error();
    if (!error) return null;
    const problem = problemOf(error);
    if (problem.code === 'query_too_long') return 'search.tooLong';
    return problem.status === 503 ? 'search.timeout' : 'search.failed';
  });
  protected readonly scopes = computed<SegmentedOption[]>(() =>
    SCOPES.map((value) => ({ value, label: this.i18n.translate(`search.scope.${value}`) })),
  );

  constructor() {
    effect(() => {
      this.result.status();
      untracked(() => this.more.set([]));
    });
  }

  protected options(facets: Facet[], selected: readonly string[]): FilterSelectOption[] {
    const known = new Set(facets.map((f) => f.value));
    return [
      ...facets.map((f) => ({ value: f.value, label: `${f.label} (${f.count})` })),
      ...selected.filter((v) => v && !known.has(v)).map((v) => ({ value: v, label: v })),
    ];
  }

  protected withAll(options: FilterSelectOption[], key: TranslationKey): FilterSelectOption[] {
    return [{ value: '', label: this.i18n.translate(key) }, ...options];
  }

  protected patch(change: Partial<ArchiveFilters>): void {
    this.state.set({ ...this.state.value(), ...change });
  }

  protected setScope(value: string | null): void {
    this.patch({ scope: value as SearchScope });
  }

  protected reset(): void {
    this.state.set({
      ...this.state.value(),
      state: ['archived'],
      org: '',
      year: '',
      category: '',
      format: '',
    });
  }

  protected useSuggestion(text: string): void {
    this.patch({ q: text });
  }

  protected loadMore(): void {
    this.loadingMore.set(true);
    this.api.search(archiveToQuery(this.state.applied(), this.hits().length)).subscribe({
      next: (out) => {
        this.more.update((list) => [...list, ...out.hits]);
        this.loadingMore.set(false);
      },
      error: () => this.loadingMore.set(false),
    });
  }

  protected open(hit: SearchHit): void {
    if (hit.kind === 'event') {
      void this.router.navigate(hit.foreign ? ['/archiv', hit.id] : ['/dossiers', hit.id]);
    } else if (hit.kind === 'document' && hit.foreign) {
      void this.router.navigate(['/bibliothek', 'document', hit.id]);
    } else {
      void this.router.navigateByUrl(hit.link);
    }
  }

  protected useTemplate(hit: SearchHit): void {
    void this.router.navigate(['/dossiers/neu'], { queryParams: { vorlage: hit.id } });
  }
}
