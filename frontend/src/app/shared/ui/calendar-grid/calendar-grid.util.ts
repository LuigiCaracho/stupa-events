/**
 * Date arithmetic of the calendar grid on plain `YYYY-MM-DD` day keys (local dates, never instants), so no UTC helper
 * can shift a day. A key is turned into a UTC midnight only to count days. "Today" and the wall-clock time of an
 * entry are read in `Europe/Berlin` (the one zone of the platform, PLAN 8.1).
 */
import { dateFormat } from '@core/i18n/format-locale';
import type { EventState } from '../../status-kind.util';

export type CalendarMode = 'month' | 'week';

export const CALENDAR_TZ = 'Europe/Berlin';

/** What the grid needs of an entry; the calendar endpoint's entries have all of it (M5 contract 7). */
export interface GridEntry {
  id: string;
  title: string;
  startsAt: string;
  startsOn: string;
  endsOn: string;
  allDay: boolean;
  state: EventState;
  publicStatus: 'scheduled' | 'cancelled' | 'postponed';
  organization: { short: string; colorToken: string | null } | null;
  howtoUnverified?: boolean;
}

export interface DayRange {
  from: string;
  to: string;
}

const DAY_MS = 86_400_000;

const utc = (key: string): number => Date.parse(`${key}T00:00:00Z`);
const toKey = (ms: number): string => new Date(ms).toISOString().slice(0, 10);

export function addDays(key: string, days: number): string {
  return toKey(utc(key) + days * DAY_MS);
}

/** Monday of the week that holds `key`. */
export function startOfWeek(key: string): string {
  const weekday = (new Date(utc(key)).getUTCDay() + 6) % 7;
  return addDays(key, -weekday);
}

export function firstOfMonth(key: string): string {
  return `${key.slice(0, 7)}-01`;
}

/** The 42 days (six Monday-first weeks) that show the month of `anchor`. */
export function monthDays(anchor: string): string[] {
  const start = startOfWeek(firstOfMonth(anchor));
  return Array.from({ length: 42 }, (_, i) => addDays(start, i));
}

export function weekDays(anchor: string): string[] {
  const start = startOfWeek(anchor);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

export function visibleDays(mode: CalendarMode, anchor: string): string[] {
  return mode === 'month' ? monthDays(anchor) : weekDays(anchor);
}

/** The inclusive range the endpoint is asked for (at most 42 days). */
export function gridRange(mode: CalendarMode, anchor: string): DayRange {
  const days = visibleDays(mode, anchor);
  return { from: days[0], to: days[days.length - 1] };
}

/** Previous or next period: a month starts on its first day, a week moves by seven days. */
export function shiftAnchor(mode: CalendarMode, anchor: string, direction: -1 | 1): string {
  if (mode === 'week') return addDays(anchor, 7 * direction);
  const first = new Date(utc(firstOfMonth(anchor)));
  first.setUTCMonth(first.getUTCMonth() + direction);
  return toKey(first.getTime());
}

export function sameMonth(a: string, b: string): boolean {
  return a.slice(0, 7) === b.slice(0, 7);
}

/** "Today" in the zone of the platform. */
export function todayKey(now: Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: CALENDAR_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

const byStart = (a: GridEntry, b: GridEntry): number =>
  Number(b.allDay) - Number(a.allDay) ||
  a.startsAt.localeCompare(b.startsAt) ||
  a.title.localeCompare(b.title, 'de');

/** The entries of each day they touch: all-day first, then by start; a multi-day entry appears on every day. */
export function entriesByDay(
  entries: readonly GridEntry[],
  days: readonly string[],
): Map<string, GridEntry[]> {
  const byDay = new Map<string, GridEntry[]>(days.map((d) => [d, []]));
  for (const entry of entries) {
    for (const day of days) {
      if (entry.startsOn <= day && day <= entry.endsOn) byDay.get(day)?.push(entry);
    }
  }
  byDay.forEach((list) => list.sort(byStart));
  return byDay;
}

/** The local date (`YYYY-MM-DD`) of an instant in the zone of the platform. */
export function localDay(iso: string): string {
  return todayKey(new Date(iso));
}

/** "18:30" in the zone of the platform. */
export function clockTime(iso: string): string {
  return dateFormat({
    timeZone: CALENDAR_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(Date.parse(iso));
}

const UTC_DAY = { timeZone: 'UTC' } as const;

export const dayLong = (key: string): string =>
  dateFormat({ ...UTC_DAY, weekday: 'long', day: 'numeric', month: 'long' }).format(utc(key));
export const dayShort = (key: string): string =>
  dateFormat({ ...UTC_DAY, weekday: 'short', day: 'numeric', month: 'short' }).format(utc(key));
export const weekdayShort = (key: string): string =>
  dateFormat({ ...UTC_DAY, weekday: 'short' }).format(utc(key));
const monthYearOf = (key: string): string =>
  dateFormat({ ...UTC_DAY, month: 'long', year: 'numeric' }).format(utc(key));
export const dayOfMonth = (key: string): number => Number(key.slice(8));

export function periodTitle(mode: CalendarMode, anchor: string): string {
  if (mode === 'month') return monthYearOf(anchor);
  const days = weekDays(anchor);
  return `${dayShort(days[0])} – ${dayShort(days[6])}`;
}
