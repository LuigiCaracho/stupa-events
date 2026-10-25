/** Bounding box of a GeoJSON collection (points and polygons), `[west, south, east, north]` or `null` when empty. */
import type { GeoCollection } from './map.models';

export type Bounds = readonly [number, number, number, number];

function positions(coordinates: unknown): [number, number][] {
  if (!Array.isArray(coordinates)) return [];
  if (typeof coordinates[0] === 'number') return [[coordinates[0], coordinates[1] as number]];
  return coordinates.flatMap(positions);
}

export function collectionBounds(collection: GeoCollection): Bounds | null {
  const all = collection.features.flatMap((f) => positions(f.geometry.coordinates));
  if (all.length === 0) return null;
  const lons = all.map(([lon]) => lon);
  const lats = all.map(([, lat]) => lat);
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)];
}
