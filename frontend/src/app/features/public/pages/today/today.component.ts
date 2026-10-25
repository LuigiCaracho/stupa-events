/**
 * P01 Heute (`/`, with P10 "Heute am Campus" as its first list): the next event as a hero card, today's events, the
 * next seven days, category chips that lead into the search and the way to the subscriptions. Nothing here needs a login.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { OnlineService } from '@core/browser/online.service';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { NoteComponent } from '@shared/ui/note/note.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { dayShort } from '@shared/ui/calendar-grid/calendar-grid.util';
import { BadgeComponent } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { statusView, whenText } from '../../model/event-format';
import { type Freshness, freshnessOf, standClock } from '../../model/freshness';
import type { PublicEventCard } from '../../model/public.models';
import { EventPosterComponent } from '../../ui/event-poster/event-poster.component';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { OfflineStateComponent } from '../../ui/offline-state/offline-state.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

const STAND_KEYS = {
  offline: 'public.today.stand.offline',
  stale: 'public.today.stand.stale',
  yesterday: 'public.today.stand.yesterday',
} as const;

@Component({
  selector: 'app-today-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    EmptyStateComponent,
    SearchPillComponent,
    SkeletonComponent,
    StatusTextComponent,
    BadgeComponent,
    EventPosterComponent,
    EventRowComponent,
    LinkButtonComponent,
    LoadErrorComponent,
    OfflineStateComponent,
    NoteComponent,
  ],
  templateUrl: './today.component.html',
  styleUrl: './today.component.scss',
})
export class TodayComponent {
  private readonly api = inject(PublicApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly now = Date.now();
  protected readonly online = inject(OnlineService).online;
  protected readonly standKeys = STAND_KEYS;
  protected readonly data = rxResource({ stream: () => this.api.today() });
  private readonly categories = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
  protected readonly stand = computed(() => {
    const at = resourceValue(this.data, undefined)?.generatedAt;
    return at ? { clock: standClock(at), freshness: freshnessOf(at, this.now) } : null;
  });
  protected readonly note = computed<{
    key: 'offline' | 'stale' | 'yesterday';
    clock: string;
  } | null>(() => {
    const stand = this.stand();
    if (!stand) return null;
    const key = this.noteKey(stand.freshness);
    return key ? { key, clock: stand.clock } : null;
  });
  protected readonly offlineFailure = computed(() => !!this.data.error() && !this.online());
  protected readonly today = computed(() => resourceValue(this.data, undefined)?.today ?? []);
  protected readonly days = computed(() =>
    (resourceValue(this.data, undefined)?.days ?? []).map((d) => ({
      ...d,
      label: dayShort(d.date),
    })),
  );
  protected readonly chips = computed(() =>
    (resourceValue(this.categories, undefined) ?? []).filter((c) => c.upcomingCount > 0),
  );
  protected readonly empty = computed(() => !!resourceValue(this.data, undefined) && !this.hero());

  /** The next event that is not cancelled: one that has not ended yet if there is one, else the first of the day. */
  protected readonly hero = computed<PublicEventCard | null>(() => {
    const out = resourceValue(this.data, undefined);
    if (!out) return null;
    const all = [...out.today, ...out.days.flatMap((d) => d.items)].filter(
      (c) => c.status !== 'cancelled',
    );
    return all.find((c) => Date.parse(c.endsAt) >= this.now) ?? all[0] ?? null;
  });
  protected readonly heroWhen = computed(() =>
    this.hero() ? whenText(this.hero() as PublicEventCard) : '',
  );
  protected readonly heroStatus = computed(() =>
    this.hero() ? statusView((this.hero() as PublicEventCard).status) : null,
  );

  constructor() {
    usePageTitle(() => this.i18n.translate('public.today.title'));
  }

  private noteKey(freshness: Freshness): 'offline' | 'stale' | 'yesterday' | null {
    if (freshness === 'yesterday') return 'yesterday';
    if (!this.online()) return 'offline';
    return freshness === 'stale' ? 'stale' : null;
  }

  protected ended(card: PublicEventCard): boolean {
    return Date.parse(card.endsAt) < this.now;
  }

  protected openSearch(): void {
    void this.router.navigateByUrl('/suche');
  }

  protected reload(): void {
    this.data.reload();
  }
}
