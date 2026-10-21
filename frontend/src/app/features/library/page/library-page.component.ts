/**
 * I19: the library (`/bibliothek`, `/bibliothek/:kind/:id`). A view on what other organizations and the formats shared on
 * purpose (M5 contract 5): howtos, notes, mail templates and files of archived dossiers, and the master howtos. List
 * with search and facets (category, organization, year, kind), detail beside it. The library never holds a text itself;
 * the list carries titles and sources only.
 */
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { createUrlState } from '@shared/url-state';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { ListDetailLayoutComponent } from '@shared/ui/list-detail/list-detail-layout.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import type { Facet } from '../../archive/model/archive.models';
import { LibraryApi } from '../api/library-api.service';
import { LibraryDetailComponent } from '../detail/library-detail.component';
import type { LibraryItem, LibraryKind, LibraryPage } from '../model/library.models';
import {
  type LibraryFilters,
  NO_LIBRARY_FILTERS,
  activeLibraryFilters,
  libraryFromParams,
  libraryToParams,
  libraryToQuery,
} from './library-filters';
import { resourceValue } from '@core/api/resource-value';

const EMPTY: LibraryPage = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
  facets: { category: [], organization: [], year: [], kind: [] },
};

@Component({
  selector: 'app-library-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    LibraryDetailComponent,
    ListDetailLayoutComponent,
    ListItemComponent,
    NoteComponent,
    PageHeaderComponent,
    SearchPillComponent,
    SkeletonComponent,
    StickyBarComponent,
  ],
  templateUrl: './library-page.component.html',
  styleUrl: './library-page.component.scss',
})
export class LibraryPageComponent {
  private readonly api = inject(LibraryApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);

  protected readonly state = createUrlState<LibraryFilters>({
    parse: libraryFromParams,
    serialize: libraryToParams,
    typing: (a, b) => a.q !== b.q,
  });
  private readonly params = toSignal(this.route.paramMap, { initialValue: this.route.snapshot.paramMap });
  protected readonly openKind = computed<LibraryKind | null>(() => {
    const kind = this.params().get('kind');
    return kind === 'document' || kind === 'attachment' ? kind : null;
  });
  protected readonly openId = computed(() => (this.openKind() ? this.params().get('id') : null));

  protected readonly page = rxResource({
    params: () => this.state.applied(),
    stream: ({ params }) => this.api.list(libraryToQuery(params)),
  });
  private readonly more = signal<LibraryItem[]>([]);
  protected readonly loadingMore = signal(false);

  protected readonly items = computed(() => [...resourceValue(this.page, EMPTY).items, ...this.more()]);
  protected readonly total = computed(() => resourceValue(this.page, EMPTY).total);
  protected readonly canMore = computed(() => this.items().length < this.total());
  protected readonly facets = computed(() => resourceValue(this.page, EMPTY).facets);
  protected readonly active = computed(() => activeLibraryFilters(this.state.applied()) > 0);
  protected readonly selected = computed<LibraryItem | null>(
    () =>
      this.items().find((i) => i.kind === this.openKind() && i.id === this.openId()) ?? null,
  );
  protected readonly meta = computed(() =>
    this.page.hasValue() ? this.i18n.translate('library.count', { count: this.total() }) : null,
  );

  constructor() {
    effect(() => {
      this.page.status();
      untracked(() => this.more.set([]));
    });
  }

  protected options(
    facets: Facet[],
    allKey: TranslationKey,
    selected: string,
    label: (f: Facet) => string = (f) => f.label,
  ): FilterSelectOption[] {
    const known = new Set(facets.map((f) => f.value));
    return [
      { value: '', label: this.i18n.translate(allKey) },
      ...facets.map((f) => ({ value: f.value, label: `${label(f)} (${f.count})` })),
      ...(selected && !known.has(selected) ? [{ value: selected, label: selected }] : []),
    ];
  }

  protected kindLabel(f: Facet): string {
    const key = `library.kind.${f.value}` as TranslationKey;
    return this.i18n.translate(key) === key ? f.label : this.i18n.translate(key);
  }

  protected patch(change: Partial<LibraryFilters>): void {
    this.state.set({ ...this.state.value(), ...change });
  }

  protected reset(): void {
    this.state.set({ ...NO_LIBRARY_FILTERS });
  }

  protected sub(item: LibraryItem): string {
    const sub = this.i18n.translate(`library.sub.${item.subKind}` as TranslationKey);
    const kind = sub.startsWith('library.sub.') ? item.subKind : sub;
    return [kind, item.source.organization.short, item.year].filter(Boolean).join(' · ');
  }

  protected link(item: LibraryItem): string[] {
    return ['/bibliothek', item.kind, item.id];
  }

  protected closeDetail(): void {
    void this.router.navigate(['/bibliothek'], { queryParamsHandling: 'preserve' });
  }

  protected loadMore(): void {
    this.loadingMore.set(true);
    this.api.list(libraryToQuery(this.state.applied(), this.items().length)).subscribe({
      next: (out) => {
        this.more.update((list) => [...list, ...out.items]);
        this.loadingMore.set(false);
      },
      error: () => this.loadingMore.set(false),
    });
  }
}
