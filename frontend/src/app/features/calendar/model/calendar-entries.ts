/**
 * Maps the entries of the calendar endpoint to the entries of the grid. `startsOn`/`endsOn` are local dates; where the server
 * leaves them out (a timed dossier) they come from the instants in `Europe/Berlin`. An entry that ends exactly at midnight
 * ends on the day before, so it does not spill into an empty day.
 */
import { type GridEntry, localDay } from '@shared/ui/calendar-grid/calendar-grid.util';
import type { CalendarEntry } from './calendar.models';

const MINUTE_MS = 60_000;

export function toGridEntry(entry: CalendarEntry): GridEntry {
  const startsOn = entry.startsOn ?? localDay(entry.startsAt);
  const lastInstant = new Date(Date.parse(entry.endsAt) - MINUTE_MS).toISOString();
  const endsOn = entry.endsOn ?? localDay(lastInstant);
  return { ...entry, startsOn, endsOn: endsOn < startsOn ? startsOn : endsOn };
}
