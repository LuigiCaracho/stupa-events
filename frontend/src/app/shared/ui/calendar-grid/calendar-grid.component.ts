/**
 * Calendar grid (M5 contract 7). Pattern from STUPA-Workflow@93c33d6 frontend/src/app/features/meetings/meetings-calendar
 * (rewritten, no code copied), decoupled from meetings: any `GridEntry` list. Month: Monday to Sunday, six rows,
 * `role=grid` with one tab stop and the arrow keys; "+n" after three entries opens the day in a side sheet. Week: seven
 * columns with the full day list. Under 768 px the grid gives way to an agenda list per day. A multi-day entry shows on
 * every day it touches. The page owns `anchor` and `mode`; the grid reports the range it shows (`rangeChange`) so the
 * page loads exactly that, and `anchorChange` when the arrow keys leave it.
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  InjectionToken,
  NgZone,
  computed,
  effect,
  inject,
  input,
  linkedSignal,
  output,
  signal,
} from '@angular/core';
import { TranslatePipe } from '@core/i18n/translate.pipe';
import { MEDIA } from '@stupa-makers/ui-kit';
import { mediaQuerySignal } from '../../../layout/media-query';
import { SideSheetComponent } from '../side-sheet/side-sheet.component';
import { CalendarEntryComponent } from './calendar-entry.component';
import {
  type CalendarMode,
  type DayRange,
  type GridEntry,
  addDays,
  dayLong,
  dayOfMonth,
  dayShort,
  entriesByDay,
  gridRange,
  sameMonth,
  startOfWeek,
  todayKey,
  visibleDays,
  weekdayShort,
} from './calendar-grid.util';

/** The clock of the grid; a test replaces it, and a page left open over midnight moves "today" on. */
export const CALENDAR_NOW = new InjectionToken<() => Date>('CALENDAR_NOW', {
  providedIn: 'root',
  factory: () => () => new Date(),
});

const MONTH_LIMIT = 3;
const CLOCK_TICK_MS = 60_000;

interface Cell {
  key: string;
  day: number;
  entries: GridEntry[];
  shown: GridEntry[];
  more: number;
  today: boolean;
  outside: boolean;
  label: string;
}

@Component({
  selector: 'app-calendar-grid',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [TranslatePipe, CalendarEntryComponent, SideSheetComponent],
  templateUrl: './calendar-grid.component.html',
  styleUrl: './calendar-grid.component.scss',
})
export class CalendarGridComponent {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly now = inject(CALENDAR_NOW);

  readonly entries = input<readonly GridEntry[]>([]);
  readonly mode = input<CalendarMode>('month');
  /** Any day inside the shown period, `YYYY-MM-DD`. */
  readonly anchor = input.required<string>();

  readonly entryOpen = output<string>();
  readonly rangeChange = output<DayRange>();
  readonly anchorChange = output<string>();

  protected readonly phone = mediaQuerySignal(MEDIA.phone);
  protected readonly clock = signal(this.now());
  protected readonly today = computed(() => todayKey(this.clock()));
  protected readonly focusDay = linkedSignal(() => this.anchor());
  protected readonly sheetDay = signal<string | null>(null);

  private readonly days = computed(() => visibleDays(this.mode(), this.anchor()));
  /** The entries of one visible day; a day outside the grid (the closed sheet) has none. */
  private entriesOf(key: string | null): GridEntry[] {
    return (key && this.byDay().get(key)) || [];
  }

  private readonly tabDay = computed(() =>
    this.days().includes(this.focusDay()) ? this.focusDay() : this.days()[0],
  );
  private readonly byDay = computed(() => entriesByDay(this.entries(), this.days()));
  private readonly range = computed(() => gridRange(this.mode(), this.anchor()), {
    equal: (a, b) => a.from === b.from && a.to === b.to,
  });

  protected readonly weekdays = computed(() => this.days().slice(0, 7).map(weekdayShort));
  protected readonly rows = computed<Cell[][]>(() => {
    const limit = this.mode() === 'month' ? MONTH_LIMIT : Number.POSITIVE_INFINITY;
    const cells = this.days().map<Cell>((key) => {
      const entries = this.entriesOf(key);
      return {
        key,
        day: dayOfMonth(key),
        entries,
        shown: entries.slice(0, limit),
        more: Math.max(0, entries.length - limit),
        today: key === this.today(),
        outside: this.mode() === 'month' && !sameMonth(key, this.anchor()),
        label: dayLong(key),
      };
    });
    return Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7));
  });
  protected readonly agenda = computed(() =>
    this.days()
      .filter((key) => this.mode() === 'week' || sameMonth(key, this.anchor()))
      .map((key) => ({ key, label: dayShort(key), entries: this.entriesOf(key) }))
      .filter((day) => day.entries.length > 0),
  );
  protected readonly sheetEntries = computed(() => this.entriesOf(this.sheetDay()));
  protected readonly sheetTitle = computed(() =>
    this.sheetDay() ? dayLong(this.sheetDay()!) : '',
  );

  constructor() {
    effect(() => this.rangeChange.emit(this.range()));
    const zone = inject(NgZone);
    const timer = zone.runOutsideAngular(() =>
      setInterval(() => {
        const next = this.now();
        if (todayKey(next) !== this.today()) zone.run(() => this.clock.set(next));
      }, CLOCK_TICK_MS),
    );
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected openCell(cell: Cell): void {
    this.focusDay.set(cell.key);
    if (cell.entries.length === 1) this.entryOpen.emit(cell.entries[0].id);
    else if (cell.entries.length > 1) this.sheetDay.set(cell.key);
  }

  protected openEntry(id: string): void {
    this.sheetDay.set(null);
    this.entryOpen.emit(id);
  }

  protected onKey(event: KeyboardEvent, cell: Cell): void {
    const step = KEY_STEPS[event.key];
    if (step !== undefined) {
      event.preventDefault();
      this.moveFocus(typeof step === 'number' ? addDays(cell.key, step) : step(cell.key));
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      this.openCell(cell);
    }
  }

  /** Focus moves at once inside the grid, so a quick second key starts from the new day; a day of another month waits for its render. */
  private moveFocus(key: string): void {
    this.focusDay.set(key);
    const range = this.range();
    const cell = (): HTMLElement | null =>
      this.host.nativeElement.querySelector<HTMLElement>(`[data-day="${key}"]`);
    if (key < range.from || key > range.to) {
      this.anchorChange.emit(key);
      queueMicrotask(() => setTimeout(() => cell()?.focus()));
      return;
    }
    cell()?.focus();
  }

  protected tabIndex(key: string): number {
    return key === this.tabDay() ? 0 : -1;
  }
}

const KEY_STEPS: Record<string, number | ((key: string) => string)> = {
  ArrowLeft: -1,
  ArrowRight: 1,
  ArrowUp: -7,
  ArrowDown: 7,
  PageUp: -28,
  PageDown: 28,
  Home: (key) => startOfWeek(key),
  End: (key) => addDays(startOfWeek(key), 6),
};
