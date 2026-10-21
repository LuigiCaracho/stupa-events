/**
 * I04: dossier list (`/dossiers`, `/dossiers/:id`, `/dossiers/neu`). The same filters as the board, one row per dossier
 * (day, title, organization, state as text, number of blockers). Wide screens show the open dossier (the child route)
 * beside the list; narrow screens show one view at a time. On `/dossiers/neu` the dialog I05 opens over the list; with
 * `?vorlage=` or `?format=` (or the second tab) it is I06 "Neu aus Vorlage". "Kalender" leads to `/kalender` with the filters.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { ListDetailLayoutComponent } from '@shared/ui/list-detail/list-detail-layout.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { eventStateStatus } from '@shared/status-kind.util';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { filter, map, startWith } from 'rxjs/operators';
import { createFilterState } from '../../pipeline/filters/filter-state';
import { PipelineFiltersComponent } from '../../pipeline/filters/pipeline-filters.component';
import {
  NO_FILTERS,
  activeFilterCount,
  filtersToQuery,
} from '../../pipeline/filters/pipeline-filters';
import type { EventCard } from '../api/board.models';
import { formatEventDay } from '../api/event-time';
import { EventsApi } from '../api/events-api.service';
import { CloneDialogComponent } from '../clone/clone-dialog.component';
import { NewEventDialogComponent } from '../new-event/new-event-dialog.component';

const PAGE = 100;

@Component({
  selector: 'app-dossier-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterOutlet,
    TranslatePipe,
    ButtonComponent,
    CloneDialogComponent,
    EmptyStateComponent,
    ListDetailLayoutComponent,
    ListItemComponent,
    NewEventDialogComponent,
    NoteComponent,
    PageHeaderComponent,
    PipelineFiltersComponent,
    SkeletonComponent,
    StatusTextComponent,
    StickyBarComponent,
  ],
  templateUrl: './dossier-list.component.html',
  styleUrl: './dossier-list.component.scss',
})
export class DossierListComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly newOpen = this.route.snapshot.data['newEvent'] === true;
  protected readonly templateId = this.route.snapshot.queryParamMap.get('vorlage');
  protected readonly formatSlug = this.route.snapshot.queryParamMap.get('format');
  /** "Neu" or "Aus Vorlage" in the dialog of `/dossiers/neu`; a template or a format in the URL starts on the second. */
  protected readonly newMode = signal<'blank' | 'template'>(
    this.templateId || this.formatSlug || this.route.snapshot.queryParamMap.get('modus') === 'vorlage'
      ? 'template'
      : 'blank',
  );
  protected readonly state = createFilterState();
  protected readonly limit = signal(PAGE);

  protected readonly selectedId = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      startWith(null),
      map(() => this.openId()),
    ),
    { initialValue: this.openId() },
  );

  protected readonly events = rxResource({
    params: () => ({ filters: this.state.applied(), limit: this.limit() }),
    stream: ({ params }) =>
      this.api.listCards({ ...filtersToQuery(params.filters), limit: params.limit }),
  });

  protected readonly rows = computed(() =>
    this.events.hasValue() ? this.events.value().items : [],
  );
  protected readonly more = computed(
    () => this.events.hasValue() && this.events.value().total > this.rows().length,
  );
  protected readonly meta = computed(() =>
    this.events.hasValue()
      ? this.i18n.translate('dossiers.count', { count: this.events.value().total })
      : null,
  );
  protected readonly filtered = computed(
    () => activeFilterCount(this.state.applied()) > 0 || this.state.applied().view !== 'active',
  );

  /** The id of the open dossier; the child route has no snapshot yet while the list is being created. */
  private openId(): string | null {
    return this.route.firstChild?.snapshot?.paramMap.get('id') ?? null;
  }

  protected showMore(): void {
    this.limit.update((n) => n + PAGE);
  }

  protected reset(): void {
    this.state.set({ ...NO_FILTERS });
  }

  protected when(card: EventCard): string {
    return formatEventDay(card.startsAt, card.tzid);
  }

  protected sub(card: EventCard): string {
    return [card.organization?.short ?? this.i18n.translate('dossiers.noOrg'), card.venueLabel]
      .filter(Boolean)
      .join(' · ');
  }

  protected status(card: EventCard) {
    return eventStateStatus(card.state);
  }

  protected openNew(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }

  protected closeNew(): void {
    void this.router.navigateByUrl('/dossiers');
  }

  protected openCalendar(): void {
    void this.router.navigate(['/kalender'], { queryParamsHandling: 'preserve' });
  }

  protected created(id: string): void {
    void this.router.navigate(['/dossiers', id]);
  }

  protected closeDetail(): void {
    void this.router.navigate(['/dossiers'], { queryParamsHandling: 'preserve' });
  }
}
