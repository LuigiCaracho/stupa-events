/**
 * The start page `/dossiers` (M5b contract 10.2): "Neues Event" and "Neu aus Vorlage" side by side, filter chips
 * (organization, category, state, year, "Nur meine") in the URL, the switch Liste | Kalender and either one card per
 * event or the calendar. On `/dossiers/neu` the dialog I05 opens over the list; with `?vorlage=` or `?format=` (or
 * `?modus=vorlage`) it is I06 "Neu aus Vorlage".
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { PageHeaderComponent } from '@shared/ui/page-header/page-header.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StickyBarComponent } from '@shared/ui/sticky-bar/sticky-bar.component';
import { createUrlState } from '@shared/url-state';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { CalendarViewComponent } from '../../calendar/view/calendar-view.component';
import { CloneDialogComponent } from '../clone/clone-dialog.component';
import { EventsApi } from '../api/events-api.service';
import {
  type EventFilters,
  NO_FILTERS,
  activeFilterCount,
  eventFiltersCodec,
  filtersToQuery,
} from '../filters/event-filters';
import { EventFiltersComponent } from '../filters/event-filters.component';
import { NewEventDialogComponent } from '../new-event/new-event-dialog.component';
import { EventCardComponent } from './event-card.component';

const PAGE = 50;

@Component({
  selector: 'app-dossier-list',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslatePipe,
    ButtonComponent,
    CalendarViewComponent,
    CloneDialogComponent,
    EmptyStateComponent,
    EventCardComponent,
    EventFiltersComponent,
    NewEventDialogComponent,
    NoteComponent,
    PageHeaderComponent,
    SegmentedComponent,
    SkeletonComponent,
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
  protected readonly newMode = signal<'blank' | 'template'>(
    this.templateId ||
      this.formatSlug ||
      this.route.snapshot.queryParamMap.get('modus') === 'vorlage'
      ? 'template'
      : 'blank',
  );
  protected readonly state = createUrlState(eventFiltersCodec);
  protected readonly limit = signal(PAGE);

  protected readonly events = rxResource({
    params: () => {
      const filters = this.state.applied();
      return filters.view === 'list' ? { filters, limit: this.limit() } : undefined;
    },
    stream: ({ params }) =>
      this.api.listCards({ ...filtersToQuery(params.filters), limit: params.limit }),
  });

  protected readonly rows = computed(() => {
    const items = this.events.hasValue() ? this.events.value().items : [];
    return this.state.applied().state === 'cancelled'
      ? items.filter((card) => card.publicStatus === 'cancelled')
      : items;
  });
  protected readonly more = computed(
    () => this.events.hasValue() && this.events.value().total > this.events.value().items.length,
  );
  protected readonly meta = computed(() =>
    this.events.hasValue() && this.state.applied().view === 'list'
      ? this.i18n.translate('dossiers.count', { count: this.rows().length })
      : null,
  );
  protected readonly filtered = computed(() => activeFilterCount(this.state.applied()) > 0);
  protected readonly views = computed<SegmentedOption[]>(() =>
    (['list', 'calendar'] as const).map((value) => ({
      value,
      label: this.i18n.translate(`dossiers.view.${value}`),
    })),
  );

  protected setView(value: string | null): void {
    this.state.set({ ...this.state.value(), view: value === 'calendar' ? 'calendar' : 'list' });
  }

  protected showMore(): void {
    this.limit.update((n) => n + PAGE);
  }

  protected reset(): void {
    this.state.set({ ...NO_FILTERS, view: this.state.value().view } satisfies EventFilters);
  }

  protected openNew(): void {
    void this.router.navigateByUrl('/dossiers/neu');
  }

  protected openTemplate(): void {
    void this.router.navigateByUrl('/dossiers/neu?modus=vorlage');
  }

  protected closeNew(): void {
    void this.router.navigateByUrl('/dossiers');
  }

  protected created(id: string): void {
    void this.router.navigate(['/dossiers', id]);
  }
}
