/** Pure helpers of the world map page (P11): the year range, the list rows and the client-side distance order. */
import { distanceKm } from '@shared/ui/map/geo-distance';
import type { GeoCollection, MapPin } from '@shared/ui/map/map.models';
import type { PublicMapCollection, PublicMapFeature } from './map.models';

export interface MapRow {
  feature: PublicMapFeature;
  km: number | null;
}

export const asGeo = (collection: PublicMapCollection | undefined): GeoCollection => ({
  type: 'FeatureCollection',
  features: (collection?.features ?? []) as unknown as GeoCollection['features'],
});

/** `from`/`to` days of a calendar year, or nothing for "all years". */
export function yearRange(year: number | null): { from?: string; to?: string } {
  return year ? { from: `${year}-01-01`, to: `${year}-12-31` } : {};
}

/** Selectable years, newest first, `count` of them ending in `currentYear`. */
export const yearChoices = (currentYear: number, count = 5): number[] =>
  Array.from({ length: count }, (_, i) => currentYear - i);

const byStart = (past: boolean) => (a: MapRow, b: MapRow) =>
  (Date.parse(a.feature.properties.startsAt) - Date.parse(b.feature.properties.startsAt)) *
  (past ? -1 : 1);

/**
 * Rows in list order: by distance when a position is known (then ties by date), else by date, newest first for the past.
 * `only` keeps the slugs of a selected cluster.
 */
export function mapRows(
  collection: PublicMapCollection | undefined,
  position: MapPin | null,
  past: boolean,
  only: readonly string[] | null,
): MapRow[] {
  const rows = (collection?.features ?? [])
    .filter((f) => !only || only.includes(f.properties.slug))
    .map<MapRow>((feature) => ({
      feature,
      km: position
        ? distanceKm(position, {
            lat: feature.geometry.coordinates[1],
            lon: feature.geometry.coordinates[0],
          })
        : null,
    }));
  return rows.sort((a, b) =>
    a.km !== null && b.km !== null && a.km !== b.km ? a.km - b.km : byStart(past)(a, b),
  );
}
