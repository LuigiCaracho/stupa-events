/**
 * P12 Campuskarte (`/campus`): the building polygons filled by the number of public events today or this week, the
 * legend, the table as the accessible twin and the event list of the chosen building. The polygons come from our own
 * database (seeded from OpenStreetMap once); the page never asks OSM at runtime.
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { resourceValue } from '@core/api/resource-value';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { MapComponent } from '@shared/ui/map/map.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { of } from 'rxjs';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import {
  type CampusSpan,
  asCampusGeo,
  campusRange,
  campusRows,
  campusTotal,
  legendRanges,
} from '../../model/campus-view';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

@Component({
  selector: 'app-campus-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    EventRowComponent,
    LoadErrorComponent,
    MapComponent,
    NoteComponent,
    SegmentedComponent,
    SkeletonComponent,
  ],
  templateUrl: './campus.component.html',
  styleUrl: './campus.component.scss',
})
export class CampusPageComponent {
  private readonly api = inject(PublicApi);
  private readonly i18n = inject(I18nService);

  protected readonly span = signal<CampusSpan>('today');
  protected readonly building = signal<string | null>(null);
  protected readonly mapFailed = signal(false);
  private readonly range = computed(() => campusRange(this.span()));

  protected readonly data = rxResource({
    params: () => this.range(),
    stream: ({ params }) => this.api.campusBuildings(params),
  });
  protected readonly events = rxResource({
    params: () =>
      this.building() ? { building: this.building() as string, ...this.range() } : null,
    stream: ({ params }) =>
      params
        ? this.api.campusEvents(params.building, { from: params.from, to: params.to })
        : of(null),
  });

  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
  protected readonly geo = computed(() => asCampusGeo(this.loaded()));
  protected readonly rows = computed(() => campusRows(this.loaded()));
  protected readonly nothing = computed(() => !!this.loaded() && campusTotal(this.loaded()) === 0);
  protected readonly anyApprox = computed(() => this.rows().some((r) => r.approx));
  protected readonly chosen = computed(() =>
    this.rows().find((r) => r.buildingNo === this.building()),
  );
  protected readonly items = computed(() => resourceValue(this.events, undefined)?.items ?? []);
  protected readonly legend = legendRanges();

  protected readonly spanOptions = computed<SegmentedOption[]>(() => [
    { value: 'today', label: this.i18n.translate('public.campus.today') },
    { value: 'week', label: this.i18n.translate('public.campus.week') },
  ]);

  constructor() {
    usePageTitle(() => this.i18n.translate('public.campus.title'));
  }

  protected setSpan(value: string | null): void {
    this.span.set(value === 'week' ? 'week' : 'today');
    this.building.set(null);
  }

  protected select(no: string): void {
    this.building.set(this.building() === no ? null : no);
  }

  protected reload(): void {
    this.data.reload();
  }
}
