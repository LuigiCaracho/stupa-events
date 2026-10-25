/** Types shared by `app-map`, its helpers and the pages that feed it (GeoJSON subset, pin, test seam states). */

export type MapMode = 'events' | 'campus' | 'pick';

export type MapState = 'loading' | 'ready' | 'error';

export interface GeoFeature {
  type: 'Feature';
  geometry: { type: string; coordinates: unknown };
  properties: Record<string, unknown> | null;
}

export interface GeoCollection {
  type: 'FeatureCollection';
  features: GeoFeature[];
}

export interface MapPin {
  lat: number;
  lon: number;
}

export interface MapColors {
  accent: string;
  onAccent: string;
  text: string;
  surface: string;
  border: string;
  neutral: string;
  levels: readonly [string, string, string];
}

export const EMPTY_COLLECTION: GeoCollection = { type: 'FeatureCollection', features: [] };

/** Reutlingen city centre as `[lon, lat]`, the start view when nothing else is known. */
export const REUTLINGEN_CENTER: readonly [number, number] = [9.2043, 48.4914];

export const TILE_BASE = '/tiles';
export const STYLE_BASE = '/map-style';
export const MAP_LIB_VERSION = '6.13.0';
export const MAP_ASSET_BASE = '/map';
