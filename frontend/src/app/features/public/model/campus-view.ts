/** Pure helpers of the campus page (P12): the Berlin day range of the two time choices, table rows and the legend text. */
import { isoToZoned } from '@shared/event-time';
import { CAMPUS_STEPS } from '@shared/ui/map/map-layers';
import type { GeoCollection } from '@shared/ui/map/map.models';
import type { CampusRange, PublicCampusCollection, PublicCampusProperties } from './map.models';

export type CampusSpan = 'today' | 'week';

const addDays = (day: string, n: number): string => {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};

/** "Heute" is the Berlin day of `now`, "Diese Woche" that day plus the next six. */
export function campusRange(span: CampusSpan, now: Date = new Date()): Required<CampusRange> {
  const from = isoToZoned(now.toISOString(), 'Europe/Berlin').date;
  return { from, to: span === 'week' ? addDays(from, 6) : from };
}

export const asCampusGeo = (collection: PublicCampusCollection | undefined): GeoCollection => ({
  type: 'FeatureCollection',
  features: (collection?.features ?? []) as unknown as GeoCollection['features'],
});

const bySeed = (a: PublicCampusProperties, b: PublicCampusProperties): number =>
  a.buildingNo.localeCompare(b.buildingNo, 'de', { numeric: true });

/** Table rows: buildings with events first, then by building number. */
export function campusRows(
  collection: PublicCampusCollection | undefined,
): PublicCampusProperties[] {
  return (collection?.features ?? [])
    .map((f) => f.properties)
    .sort((a, b) => Number(b.count > 0) - Number(a.count > 0) || bySeed(a, b));
}

export const campusTotal = (collection: PublicCampusCollection | undefined): number =>
  (collection?.features ?? []).reduce((sum, f) => sum + f.properties.count, 0);

/** The number ranges of the four fill levels, "0", "1–2", "3–5", "6 und mehr". */
export function legendRanges(): { level: number; from: number; to: number | null }[] {
  const [a, b, c] = CAMPUS_STEPS;
  return [
    { level: 0, from: 0, to: 0 },
    { level: 1, from: a, to: b - 1 },
    { level: 2, from: b, to: c - 1 },
    { level: 3, from: c, to: null },
  ];
}
