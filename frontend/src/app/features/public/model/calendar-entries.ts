/** Adapters between the public calendar answer and the shared calendar grid. */
import type { GridEntry } from '@shared/ui/calendar-grid/calendar-grid.util';
import { endDay, startDay } from './event-format';
import type { PublicCalendarEntry, PublicCalendarOut } from './public.models';

/** The grid entry of a public entry: the slug is the id, the public state is always "published". */
export function toGridEntry(entry: PublicCalendarEntry): GridEntry {
  return {
    id: entry.slug,
    title: entry.title,
    startsAt: entry.startsAt,
    startsOn: startDay(entry),
    endsOn: endDay(entry),
    allDay: entry.allDay,
    state: 'published',
    publicStatus: entry.status,
    organization: null,
  };
}

/** Every event once: a multi-day event stands on each day it touches in the answer. */
export function gridEntries(out: PublicCalendarOut | null): GridEntry[] {
  const seen = new Map<string, PublicCalendarEntry>();
  for (const day of out?.days ?? []) for (const item of day.items) seen.set(item.slug, item);
  return [...seen.values()].map(toGridEntry);
}

/** The month key `YYYY-MM` that a day key belongs to. */
export const monthOf = (day: string): string => day.slice(0, 7);

/** `YYYY-MM-01` of a month key, the anchor the grid shows that month with. */
export const anchorOf = (month: string): string => `${month}-01`;
