/**
 * P11 Weltkarte (`/karte`): every public event with a coordinate as a clustered point, the time filter "Gibt es" /
 * "Gab es", category filter and the list of the hits as the accessible twin of the map. "In meiner Nähe" only sorts
 * the list in the browser and draws one local dot; the position is never part of a request (decision E30).
 */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { rxResource, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { resourceValue } from '@core/api/resource-value';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { dayKeyToDate } from '@shared/event-time';
import { DateBlockComponent } from '@shared/ui/date-block/date-block.component';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import {
  FilterSelectComponent,
  type FilterSelectOption,
} from '@shared/ui/filter-select/filter-select.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { formatDistance } from '@shared/ui/map/geo-distance';
import { MapComponent } from '@shared/ui/map/map.component';
import { NearMeService } from '@shared/ui/map/near-me.service';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent, SegmentedComponent, type SegmentedOption } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { startDay, statusView } from '../../model/event-format';
import { asGeo, mapRows, yearChoices, yearRange } from '../../model/map-view';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

@Component({
  selector: 'app-map-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    SegmentedComponent,
    DateBlockComponent,
    EmptyStateComponent,
    FilterSelectComponent,
    ListItemComponent,
    MapComponent,
    NoteComponent,
    SkeletonComponent,
    StatusTextComponent,
    LoadErrorComponent,
  ],
  templateUrl: './map.component.html',
  styleUrl: './map.component.scss',
})
export class MapPageComponent {
  private readonly api = inject(PublicApi);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly i18n = inject(I18nService);
  protected readonly near = inject(NearMeService);

  private readonly params = toSignal(this.route.queryParamMap, {
    initialValue: this.route.snapshot.queryParamMap,
  });
  protected readonly past = computed(() => this.params().get('vergangen') === '1');
  protected readonly year = computed(() => Number(this.params().get('jahr')) || null);
  protected readonly categories = computed(() => this.params().getAll('k'));

  protected readonly data = rxResource({
    params: () => ({ past: this.past(), year: this.year(), category: this.categories() }),
    stream: ({ params }) =>
      this.api.mapEvents({
        past: params.past,
        category: params.category,
        ...(params.past ? yearRange(params.year) : {}),
      }),
  });
  private readonly categoryList = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly selected = signal<string | null>(null);
  protected readonly cluster = signal<readonly string[] | null>(null);
  protected readonly mapFailed = signal(false);

  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
  protected readonly geo = computed(() => asGeo(this.loaded()));
  protected readonly rows = computed(() =>
    mapRows(this.loaded(), this.near.position(), this.past(), this.cluster()).map((row) => ({
      ...row,
      day: dayKeyToDate(
        startDay({
          startsAt: row.feature.properties.startsAt,
          startsOn: null,
          tzid: 'Europe/Berlin',
        }),
      ),
      sub: this.sub(row.feature.properties.venueName, row.km),
      status: statusView(row.feature.properties.status),
    })),
  );
  protected readonly total = computed(() => this.loaded()?.features.length ?? 0);
  protected readonly empty = computed(() => !!this.loaded() && this.total() === 0);

  protected readonly timeOptions = computed<SegmentedOption[]>(() => [
    { value: 'upcoming', label: this.i18n.translate('public.map.upcoming') },
    { value: 'past', label: this.i18n.translate('public.map.past') },
  ]);
  protected readonly timeValue = computed(() => (this.past() ? 'past' : 'upcoming'));
  protected readonly yearOptions = computed<FilterSelectOption[]>(() =>
    yearChoices(new Date().getFullYear()).map((y) => ({ value: String(y), label: String(y) })),
  );
  protected readonly categoryOptions = computed<FilterSelectOption[]>(() =>
    (resourceValue(this.categoryList, undefined) ?? []).map((c) => ({
      value: c.slug,
      label: c.name,
    })),
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.map.title'));
  }

  protected setTime(value: string | null): void {
    this.navigate({ vergangen: value === 'past' ? '1' : null, jahr: null });
  }

  protected setYear(values: readonly string[]): void {
    this.navigate({ jahr: values.at(-1) ?? null });
  }

  protected setCategories(values: readonly string[]): void {
    this.navigate({ k: values.length ? [...values] : null });
  }

  protected async nearMe(): Promise<void> {
    await this.near.request();
  }

  protected open(slug: string): void {
    void this.router.navigateByUrl(`/e/${slug}`);
  }

  protected reload(): void {
    this.data.reload();
  }

  private navigate(queryParams: Record<string, string | string[] | null>): void {
    this.cluster.set(null);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge',
    });
  }

  private sub(venue: string | null, km: number | null): string | null {
    const parts = [venue, km === null ? null : formatDistance(km, this.i18n.formatLocale())];
    return parts.filter(Boolean).join(' · ') || null;
  }
}
