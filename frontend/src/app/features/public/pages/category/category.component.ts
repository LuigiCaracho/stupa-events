/**
 * P05 Kategorie (`/k/:slug`): name and description, the subscription link, the upcoming events of the category and a
 * short review below. An unknown slug is a 404 like an unknown event.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { resourceValue } from '@core/api/resource-value';
import { rxResource } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { EmptyStateComponent } from '@shared/ui/empty-state/empty-state.component';
import { SkeletonComponent } from '@shared/ui/skeleton/skeleton.component';
import { ButtonComponent } from '@stupa-makers/ui-kit';
import { PublicApi } from '../../api/public-api.service';
import { publicErrorOf } from '../../api/public-error';
import { toApiQuery, EMPTY_FILTERS } from '../../model/search-filters';
import { pagedList } from '../../model/paged-list';
import type { PublicEventCard, PublicSearchOut } from '../../model/public.models';
import { EventRowComponent } from '../../ui/event-row/event-row.component';
import { LinkButtonComponent } from '../../ui/link-button/link-button.component';
import { LoadErrorComponent } from '../../ui/load-error/load-error.component';
import { usePageTitle } from '../../ui/page-title';

const REVIEW_LIMIT = 6;

@Component({
  selector: 'app-category-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    TranslatePipe,
    ButtonComponent,
    EmptyStateComponent,
    SkeletonComponent,
    EventRowComponent,
    LinkButtonComponent,
    LoadErrorComponent,
  ],
  templateUrl: './category.component.html',
  styleUrl: './category.component.scss',
})
export class CategoryPageComponent {
  private readonly api = inject(PublicApi);
  private readonly i18n = inject(I18nService);

  readonly slug = input.required<string>();
  private readonly categories = rxResource({ stream: () => this.api.categories() });

  protected readonly category = computed(
    () => resourceValue(this.categories, undefined)?.find((c) => c.slug === this.slug()) ?? null,
  );
  protected readonly notFound = computed(
    () => !!resourceValue(this.categories, undefined) && !this.category(),
  );
  protected readonly error = computed(() =>
    this.categories.error() ? publicErrorOf(this.categories.error()) : null,
  );

  protected readonly upcoming = pagedList<string, PublicEventCard, PublicSearchOut>({
    params: () => this.slug(),
    fetch: (slug, cursor) =>
      this.api.events(toApiQuery({ ...EMPTY_FILTERS, category: [slug] }, cursor)),
  });
  private readonly review = rxResource({
    params: () => this.slug(),
    stream: ({ params }) =>
      this.api.events({ category: [params], past: true, limit: REVIEW_LIMIT }),
  });
  protected readonly reviewItems = computed(
    () => resourceValue(this.review, undefined)?.items ?? [],
  );

  constructor() {
    usePageTitle(() => this.category()?.name ?? null);
  }

  protected reload(): void {
    this.categories.reload();
    this.upcoming.reload();
  }
}
