/**
 * Display helpers of the public pages: when, where and in which state an event is, and the semester it belongs to.
 * Times are always shown in the zone of the event (`tzid`, Europe/Berlin), never in the browser zone.
 */
import { dateWords } from '@core/i18n/format-locale';
import type { StatusKind } from '@shared/status-kind.util';
import { formatClock, formatEventDate, isoToZoned } from '@shared/event-time';
import type { TranslationKey } from '@core/i18n/translations';
import type { PublicEventCard, PublicStatus } from './public.models';

type Timed = Pick<
  PublicEventCard,
  'startsAt' | 'endsAt' | 'allDay' | 'startsOn' | 'endsOn' | 'tzid'
>;
type Starting = Pick<Timed, 'startsAt' | 'startsOn'> & { tzid?: string };
type Ending = Pick<Timed, 'endsAt' | 'endsOn'> & { tzid?: string };

const BERLIN = 'Europe/Berlin';

/** The calendar day an event starts on in its own zone (`YYYY-MM-DD`). */
export const startDay = (e: Starting): string =>
  e.startsOn ?? isoToZoned(e.startsAt, e.tzid ?? BERLIN).date;

/** The calendar day an event ends on in its own zone (`YYYY-MM-DD`). */
export const endDay = (e: Ending): string =>
  e.endsOn ?? isoToZoned(e.endsAt, e.tzid ?? BERLIN).date;

/** "Do., 22. Okt. 2026, 20:00 bis 22:30 Uhr", a two-day span, or "… (ganztägig)"; in English "Thu, 22 Oct 2026, 20:00 to 22:30". */
export function whenText(e: Timed): string {
  const tz = e.tzid;
  const w = dateWords();
  if (e.allDay) {
    const start = formatEventDate(e.startsAt, tz);
    return endDay(e) !== startDay(e)
      ? `${start} ${w.to} ${formatEventDate(e.endsAt, tz)}`
      : `${start} (${w.allDay})`;
  }
  const day = formatEventDate(e.startsAt, tz);
  const from = formatClock(e.startsAt, tz);
  if (e.endsAt === e.startsAt) return `${day}, ${w.clock(from)}`;
  if (endDay(e) === startDay(e))
    return `${day}, ${from} ${w.to} ${w.clock(formatClock(e.endsAt, tz))}`;
  return `${day}, ${w.clock(from)} ${w.to} ${formatEventDate(e.endsAt, tz)}, ${w.clock(formatClock(e.endsAt, tz))}`;
}

/** The time of day of a row ("20:00"), or `null` for an all-day event. */
export function clockOf(e: Timed): string | null {
  return e.allDay ? null : formatClock(e.startsAt, e.tzid);
}

export interface StatusView {
  kind: StatusKind;
  key: TranslationKey;
}

/** The state of a cancelled or postponed event as text, `null` for a scheduled one. */
export function statusView(status: PublicStatus): StatusView | null {
  if (status === 'cancelled') return { kind: 'error', key: 'publicStatus.cancelled' };
  if (status === 'postponed') return { kind: 'warn', key: 'publicStatus.postponed' };
  return null;
}

export interface SemesterGroup {
  key: string;
  semester: 'ws' | 'sose';
  /** Year the semester starts in (WS 2025/26 gives 2025). */
  year: number;
}

/** WS runs 1 Oct to 31 Mar, SoSe 1 Apr to 30 Sep, by the Berlin start day. */
export function semesterOf(startsOn: string): SemesterGroup {
  const year = Number(startsOn.slice(0, 4));
  const month = Number(startsOn.slice(5, 7));
  if (month >= 10) return { key: `ws${year}`, semester: 'ws', year };
  if (month <= 3) return { key: `ws${year - 1}`, semester: 'ws', year: year - 1 };
  return { key: `sose${year}`, semester: 'sose', year };
}

/** "Wintersemester 2025/26" or "Sommersemester 2026". */
export function semesterLabel(group: SemesterGroup): string {
  const w = dateWords();
  return group.semester === 'sose'
    ? `${w.summer} ${group.year}`
    : `${w.winter} ${group.year}/${String(group.year + 1).slice(2)}`;
}

/** Groups items in the order they come: one group per run of the same semester. */
export function groupBySemester<T extends Starting>(
  items: readonly T[],
): { group: SemesterGroup; label: string; items: T[] }[] {
  const out: { group: SemesterGroup; label: string; items: T[] }[] = [];
  for (const item of items) {
    const group = semesterOf(startDay(item));
    const last = out[out.length - 1];
    if (last?.group.key === group.key) last.items.push(item);
    else out.push({ group, label: semesterLabel(group), items: [item] });
  }
  return out;
}

/** Groups items by Berlin start day, in the order they come. */
export function groupByDay<T extends Starting>(
  items: readonly T[],
): { date: string; items: T[] }[] {
  const out: { date: string; items: T[] }[] = [];
  for (const item of items) {
    const last = out[out.length - 1];
    const date = startDay(item);
    if (last?.date === date) last.items.push(item);
    else out.push({ date, items: [item] });
  }
  return out;
}
