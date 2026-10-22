/**
 * One event as a list row (P01 "Heute am Campus", P02 results, P05, P13 uses the grid instead): date block, title,
 * "20:00 · Ort", state as text ("Abgesagt", "Verschoben"), the first category as a tag and, with `thumb`, the
 * poster thumbnail. The whole row is one link to `/e/<slug>`.
 */
import {
  ChangeDetectionStrategy,
  Component,
  booleanAttribute,
  computed,
  inject,
  input,
} from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { dayKeyToDate } from '@shared/event-time';
import { DateBlockComponent } from '@shared/ui/date-block/date-block.component';
import { ListItemComponent } from '@shared/ui/list-item/list-item.component';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import { BadgeComponent, MEDIA } from '@stupa-makers/ui-kit';
import { mediaQuerySignal } from '../../../../layout/media-query';
import { clockOf, statusView } from '../../model/event-format';
import type { PublicEventCard } from '../../model/public.models';
import { EventPosterComponent } from '../event-poster/event-poster.component';

@Component({
  selector: 'app-public-event-row',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ListItemComponent,
    DateBlockComponent,
    StatusTextComponent,
    BadgeComponent,
    EventPosterComponent,
    TranslatePipe,
  ],
  templateUrl: './event-row.component.html',
  styleUrl: './event-row.component.scss',
})
export class EventRowComponent {
  readonly card = input.required<PublicEventCard>();
  readonly thumb = input(false, { transform: booleanAttribute });
  readonly muted = input(false, { transform: booleanAttribute });
  protected readonly day = computed(() => dayKeyToDate(this.card().startsOn));
  protected readonly status = computed(() => statusView(this.card().status));
  private readonly i18n = inject(I18nService);
  protected readonly phone = mediaQuerySignal(MEDIA.phone);
  protected readonly tag = computed(() => this.card().categories[0]?.name ?? null);
  /** On a phone the tag has no room beside the title, so the category joins the sub line. */
  protected readonly sub = computed(() => {
    const c = this.card();
    const when = clockOf(c) ?? this.i18n.translate('calendar.allDay');
    return [when, c.venueName, this.phone() ? this.tag() : null].filter(Boolean).join(' · ');
  });
}
