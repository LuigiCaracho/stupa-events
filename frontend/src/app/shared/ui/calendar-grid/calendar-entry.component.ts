/**
 * One entry of the calendar as a button: time (or "ganztägig"), title, organization, and the state as text unless it is
 * `live` or `approved` (colour alone never carries a state). The stripe at the start edge takes the colour token of the
 * organization. Used by the grid cells, the day sheet and the agenda list.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import type { TranslationKey } from '@core/i18n/translations';
import { eventStateStatus, type StatusKind } from '../../status-kind.util';
import { StatusTextComponent } from '../status-text/status-text.component';
import { type GridEntry, clockTime } from './calendar-grid.util';

interface Marker {
  kind: StatusKind;
  key: TranslationKey;
}

@Component({
  selector: 'app-calendar-entry',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, StatusTextComponent],
  host: { '[class.ce--compact]': 'compact()' },
  templateUrl: './calendar-entry.component.html',
  styleUrl: './calendar-entry.component.scss',
})
export class CalendarEntryComponent {
  readonly entry = input.required<GridEntry>();
  /** Month cells: a single line of text, the rest wraps under it. */
  readonly compact = input(false);
  /** Out of the grid (sheet, agenda) the button is a normal tab stop; in a grid cell the cell is. */
  readonly focusable = input(true);
  /** The day this button stands on; the time shows only on the first day of a multi-day entry. */
  readonly day = input<string | null>(null);

  readonly open = output<string>();

  protected readonly tint = computed(() => {
    const token = this.entry().organization?.colorToken;
    return token ? `var(--cal-${token}, var(--color-border-strong))` : 'var(--color-border-strong)';
  });
  protected readonly time = computed(() => {
    const e = this.entry();
    if (this.day() && this.day() !== e.startsOn) return null;
    return e.allDay ? null : clockTime(e.startsAt);
  });
  protected readonly continues = computed(() => !!this.day() && this.day() !== this.entry().startsOn);
  protected readonly marker = computed<Marker | null>(() => {
    const e = this.entry();
    if (e.publicStatus === 'cancelled') return { kind: 'error', key: 'publicStatus.cancelled' };
    if (e.publicStatus === 'postponed') return { kind: 'warn', key: 'publicStatus.postponed' };
    if (e.state === 'live' || e.state === 'approved') return null;
    const status = eventStateStatus(e.state);
    return { kind: status.kind, key: status.key };
  });
}
