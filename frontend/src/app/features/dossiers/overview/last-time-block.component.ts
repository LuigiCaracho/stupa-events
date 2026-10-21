/**
 * "Letztes Mal" on the dossier overview (M5 contract 4.3): attendance, costs, revenue and retrospective of the earlier
 * edition (the template, or the latest archived edition of the same format), and for an own organization the panel
 * "Angebote der letzten Auflage". The quotes request is the one of M4; only a 200 shows the panel, an answer of another
 * organization (404) leaves it out.
 */
import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { QuoteTableComponent } from '@shared/ui/quote-table/quote-table.component';
import { catchError, map, of } from 'rxjs';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { LastTimeCardComponent } from '../../archive/last-time/last-time-card.component';
import type { LastTime } from '../../archive/model/archive.models';
import { AttachmentsApi } from '../api/attachments-api.service';
import type { EventDto } from '../api/event.models';
import type { QuoteGroup } from '../model/attachment.models';
import { resourceValue } from '@core/api/resource-value';

@Component({
  selector: 'app-last-time-block',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, LastTimeCardComponent, QuoteTableComponent],
  templateUrl: './last-time-block.component.html',
  styleUrl: './last-time-block.component.scss',
})
export class LastTimeBlockComponent {
  private readonly archive = inject(ArchiveApi);
  private readonly attachments = inject(AttachmentsApi);

  readonly event = input.required<EventDto>();

  protected readonly lastTime = rxResource({
    params: () => {
      const e = this.event();
      return e.derivedFromId || e.formatId ? e.id : undefined;
    },
    stream: ({ params }) => this.archive.lastTime(params).pipe(catchError(() => of(null))),
  });
  protected readonly value = computed(() => resourceValue<LastTime | null>(this.lastTime, null));
  protected readonly quotes = rxResource({
    params: () => {
      const lt = this.value();
      return lt?.source.own ? lt.source.id : undefined;
    },
    stream: ({ params }) =>
      this.attachments.quotes(params).pipe(
        map((q) => q.groups.filter((g) => g.quotes.length > 0)),
        catchError(() => of([] as QuoteGroup[])),
      ),
  });
  protected readonly groups = computed(() => resourceValue(this.quotes, [] as QuoteGroup[]));
}
