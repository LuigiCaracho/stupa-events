/**
 * One event in the list (M5b contract 10.2): thumbnail or placeholder, title as the link, day, organization and
 * venue, the state as text and a small mark where the event is published without a picture or its howto is unchecked.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { eventStateStatus } from '@shared/status-kind.util';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { IconComponent } from '@stupa-makers/ui-kit';
import type { EventCard } from '../api/card.models';
import { formatEventDay } from '../api/event-time';
import { EventsApi } from '../api/events-api.service';

@Component({
  selector: 'app-event-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, TranslatePipe, IconComponent, StatusTextComponent],
  templateUrl: './event-card.component.html',
  styleUrl: './event-card.component.scss',
})
export class EventCardComponent {
  private readonly api = inject(EventsApi);
  private readonly i18n = inject(I18nService);

  readonly card = input.required<EventCard>();

  protected readonly failed = signal(false);
  protected readonly state = computed(() => eventStateStatus(this.card().state));
  protected readonly publicMark = computed(() => {
    const status = this.card().publicStatus;
    if (status === 'scheduled') return null;
    return {
      kind: status === 'cancelled' ? ('error' as const) : ('warn' as const),
      key: status === 'cancelled' ? ('publicStatus.cancelled' as const) : ('publicStatus.postponed' as const),
    };
  });
  protected readonly thumb = computed(() =>
    this.card().hasPoster && !this.failed() ? this.api.posterUrl(this.card().id, 'thumb400') : null,
  );
  protected readonly noImageMark = computed(
    () => this.card().state === 'published' && !this.card().hasPoster,
  );
  protected readonly when = computed(() => formatEventDay(this.card().startsAt, this.card().tzid));
  protected readonly sub = computed(() =>
    [
      this.card().organization?.short ?? this.i18n.translate('dossiers.noOrg'),
      this.card().venueLabel,
    ]
      .filter(Boolean)
      .join(' · '),
  );
}
