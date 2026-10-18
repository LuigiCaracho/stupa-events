/**
 * One card of the pipeline board: title, day, organization and venue, the status line (planned release, cancelled,
 * postponed), the first blockers of the next transition and the avatar of the person who created the dossier.
 * The card is a button that opens the dossier; the keyboard lift sets `aria-pressed`.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { I18nService } from '@core/i18n/i18n.service';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import type { StatusKind } from '@shared/status-kind.util';
import { AvatarComponent } from '@shared/ui/avatar/avatar.component';
import { reasonText } from '@shared/ui/guard-list/reason-text';
import { StatusTextComponent } from '@shared/ui/status-text/status-text.component';
import type { EventCard } from '../../dossiers/api/board.models';
import { formatEventDay, formatShortDate } from '../../dossiers/api/event-time';

interface StatusLine {
  kind: StatusKind;
  text: string;
}

@Component({
  selector: 'app-board-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, AvatarComponent, StatusTextComponent],
  templateUrl: './board-card.component.html',
  styleUrl: './board-card.component.scss',
})
export class BoardCardComponent {
  private readonly i18n = inject(I18nService);

  readonly card = input.required<EventCard>();
  readonly lifted = input(false);
  readonly describedBy = input<string | null>(null);

  readonly open = output<EventCard>();

  protected readonly day = computed(() => formatEventDay(this.card().startsAt, this.card().tzid));
  protected readonly place = computed(() =>
    [
      this.card().organization?.short ?? this.i18n.translate('dossiers.noOrg'),
      this.card().venueLabel,
    ]
      .filter(Boolean)
      .join(' · '),
  );
  protected readonly author = computed(() => this.card().createdBy.displayName ?? '?');
  protected readonly shown = computed(() => this.card().blockers.slice(0, 3));
  protected readonly more = computed(() =>
    Math.max(0, this.card().blockerCount - this.shown().length),
  );

  protected readonly status = computed<StatusLine | null>(() => {
    const c = this.card();
    const t = (key: TranslationKey, params?: Record<string, string | number>): string =>
      this.i18n.translate(key, params);
    if (c.publicStatus === 'cancelled') return { kind: 'error', text: t('publicStatus.cancelled') };
    if (c.publicStatus === 'postponed') return { kind: 'warn', text: t('publicStatus.postponed') };
    if (c.state === 'approved') {
      return c.publishAt
        ? {
            kind: 'neutral',
            text: t('board.plannedFrom', { date: formatShortDate(c.publishAt, c.tzid) }),
          }
        : { kind: 'neutral', text: t('event.state.approved') };
    }
    return c.state === 'live' ? { kind: 'accent', text: t('event.state.live') } : null;
  });

  protected reason(r: EventCard['blockers'][number]): string {
    return reasonText(this.i18n, r);
  }
}
