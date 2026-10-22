/**
 * P13 Rückblick (`/rueckblick?year=`): past events that have a poster, as a poster grid grouped by semester, with the
 * years as chips. Cancelled events stay visible with their state as text.
 */
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { PublicApi } from '../../api/public-api.service';
import { formatEventDate } from '@shared/event-time';
import { groupBySemester, statusView } from '../../model/event-format';
import { pagedList } from '../../model/paged-list';
import type { PublicArchiveOut, PublicEventCard } from '../../model/public.models';
import { EventPosterComponent } from '../../ui/event-poster/event-poster.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

const PAGE_SIZE = 24;

@Component({
  selector: 'app-review-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    SkeletonComponent,
    StatusTextComponent,
    EventPosterComponent,
    LoadErrorComponent,
  ],
  templateUrl: './review.component.html',
  styleUrl: './review.component.scss',
})
export class ReviewPageComponent {
  private readonly api = inject(PublicApi);
  private readonly route = inject(ActivatedRoute);
  private readonly i18n = inject(I18nService);

  private readonly query = toSignal(this.route.queryParamMap, {
    initialValue: this.route.snapshot.queryParamMap,
  });
  private readonly requested = computed(() => {
    const year = Number(this.query().get('year'));
    return Number.isInteger(year) && year >= 2000 && year <= 2100 ? year : undefined;
  });

  protected readonly list = pagedList<
    { year: number | undefined },
    PublicEventCard,
    PublicArchiveOut
  >({
    params: () => ({ year: this.requested() }),
    fetch: (p, cursor) => this.api.archive({ year: p.year, limit: PAGE_SIZE, cursor }),
  });
  protected readonly years = computed(() => this.list.first()?.years ?? []);
  protected readonly shownYear = computed(
    () => this.list.first()?.year ?? this.requested() ?? null,
  );
  protected readonly groups = computed(() =>
    groupBySemester(this.list.items()).map((g) => ({
      ...g,
      items: g.items.map((card) => ({
        card,
        date: formatEventDate(card.startsAt, card.tzid),
        status: statusView(card.status),
      })),
    })),
  );
  protected readonly empty = computed(() => !!this.list.first() && this.list.items().length === 0);

  constructor() {
    usePageTitle(() => this.i18n.translate('public.review.title'));
  }
}
