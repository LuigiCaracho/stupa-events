/**
 * P01 Heute (`/`, with P10 "Heute am Campus" as its first list): the next event as a hero card, today's events, the
 * next seven days, category chips that lead into the search and the way to the subscriptions. Nothing here needs a login.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { SearchPillComponent } from '@shared/ui/search-pill/search-pill.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { dayShort } from '@shared/ui/calendar-grid/calendar-grid.util';
import { BadgeComponent } from '@stupa-makers/ui-kit';
import { catchError, of } from 'rxjs';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { statusView, whenText } from '../../model/event-format';
import type { PublicEventCard } from '../../model/public.models';
import { EventPosterComponent } from '../../ui/event-poster/event-poster.component';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

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
  ],
  templateUrl: './today.component.html',
  styleUrl: './today.component.scss',
})
export class TodayComponent {
  private readonly api = inject(PublicApi);
  private readonly router = inject(Router);
  private readonly i18n = inject(I18nService);
  private readonly now = Date.now();
  protected readonly data = rxResource({ stream: () => this.api.today() });
  private readonly categories = rxResource({
    stream: () => this.api.categories().pipe(catchError(() => of([]))),
  });

  protected readonly loaded = computed(() => resourceValue(this.data, undefined));
  protected readonly error = computed(() =>
    this.data.error() ? publicErrorOf(this.data.error()) : null,
  );
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
