/**
 * Display helpers of the public pages: when, where and in which state an event is, and the semester it belongs to.
 * Times are always shown in the zone of the event (`tzid`, Europe/Berlin), never in the browser zone.
 */
import type { StatusKind } from '@shared/status-kind.util';
import { formatClock, formatEventDate } from '@shared/event-time';
import type { TranslationKey } from '@core/i18n/translations';
import type { PublicEventCard, PublicStatus } from './public.models';

type Timed = Pick<
  PublicEventCard,
  'startsAt' | 'endsAt' | 'allDay' | 'startsOn' | 'endsOn' | 'tzid'
>;

/** "Do., 22. Okt. 2026, 20:00 bis 22:30 Uhr", a two-day span, or "… (ganztägig)". */
export function whenText(e: Timed): string {
  const tz = e.tzid;
  if (e.allDay) {
    const start = formatEventDate(e.startsAt, tz);
    return e.endsOn !== e.startsOn
      ? `${start} bis ${formatEventDate(e.endsAt, tz)}`
      : `${start} (ganztägig)`;
  }
  const day = formatEventDate(e.startsAt, tz);
  const from = formatClock(e.startsAt, tz);
  if (e.endsAt === e.startsAt) return `${day}, ${from} Uhr`;
  if (e.endsOn === e.startsOn) return `${day}, ${from} bis ${formatClock(e.endsAt, tz)} Uhr`;
  return `${day}, ${from} Uhr bis ${formatEventDate(e.endsAt, tz)}, ${formatClock(e.endsAt, tz)} Uhr`;
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
  return group.semester === 'sose'
    ? `Sommersemester ${group.year}`
    : `Wintersemester ${group.year}/${String(group.year + 1).slice(2)}`;
}

/** Groups items in the order they come: one group per run of the same semester. */
export function groupBySemester<T extends { startsOn: string }>(
  items: readonly T[],
): { group: SemesterGroup; label: string; items: T[] }[] {
  const out: { group: SemesterGroup; label: string; items: T[] }[] = [];
  for (const item of items) {
    const group = semesterOf(item.startsOn);
    const last = out[out.length - 1];
    if (last?.group.key === group.key) last.items.push(item);
    else out.push({ group, label: semesterLabel(group), items: [item] });
  }
  return out;
}

/** Groups items by Berlin start day, in the order they come. */
export function groupByDay<T extends { startsOn: string }>(
  items: readonly T[],
): { date: string; items: T[] }[] {
  const out: { date: string; items: T[] }[] = [];
  for (const item of items) {
    const last = out[out.length - 1];
    if (last?.date === item.startsOn) last.items.push(item);
    else out.push({ date: item.startsOn, items: [item] });
  }
  return out;
}
