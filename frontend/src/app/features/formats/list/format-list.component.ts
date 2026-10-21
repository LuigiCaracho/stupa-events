/**
 * I18, list side (`/formate`): all formats with organization, number of editions and the review state of their master
 * howto ("Anleitung geprüft am …" or the warning when it is older than twelve months). The open format
 * (`/formate/:slug`, the child route) shows beside the list on a wide screen.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { LocalizedDatePipe } from '@core/i18n/localized-date.pipe';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { ListDetailLayoutComponent } from '@shared/ui/list-detail/list-detail-layout.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { debounceTime, distinctUntilChanged, filter, map, startWith } from 'rxjs/operators';
import { toObservable } from '@angular/core/rxjs-interop';
import { FormatsApi } from '../api/formats-api.service';
import type { FormatCard, FormatPage } from '../model/format.models';
import { resourceValue } from '@core/api/resource-value';

const SEARCH_DELAY_MS = 250;
const EMPTY: FormatPage = { items: [], total: 0, limit: 100, offset: 0 };

@Component({
  selector: 'app-format-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterOutlet,
    LocalizedDatePipe,
    TranslatePipe,
    EmptyStateComponent,
    ListDetailLayoutComponent,
    ListItemComponent,
    NoteComponent,
    PageHeaderComponent,
    SearchPillComponent,
    SkeletonComponent,
    StatusTextComponent,
    StickyBarComponent,
  ],
  templateUrl: './format-list.component.html',
  styleUrl: './format-list.component.scss',
})
export class FormatListComponent {
  private readonly api = inject(FormatsApi);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly i18n = inject(I18nService);

  protected readonly q = signal('');
  private readonly applied = toSignal(
    toObservable(this.q).pipe(debounceTime(SEARCH_DELAY_MS), distinctUntilChanged()),
    { initialValue: '' },
  );

  protected readonly selectedSlug = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      startWith(null),
      map(() => this.openSlug()),
    ),
    { initialValue: this.openSlug() },
  );

  protected readonly formats = rxResource({
    params: () => this.applied().trim(),
    stream: ({ params }) => this.api.list({ q: params || undefined, limit: 100 }),
  });
  protected readonly rows = computed(() => resourceValue(this.formats, EMPTY).items);
  protected readonly meta = computed(() =>
    this.formats.hasValue()
      ? this.i18n.translate('format.count', { count: this.formats.value().total })
      : null,
  );

  private openSlug(): string | null {
    return this.route.firstChild?.snapshot?.paramMap.get('slug') ?? null;
  }

  protected sub(card: FormatCard): string {
    return `${card.organization.short} · ${this.i18n.translate('format.editions', { count: card.editions })}`;
  }

  protected closeDetail(): void {
    void this.router.navigate(['/formate']);
  }
}
