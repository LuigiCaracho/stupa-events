/** Wire types of the public map API (C contract 4.1 and 4.2): GeoJSON, camelCase properties, root-relative URLs. */
import type { PublicStatus } from './public.models';

export type VenuePrecision = 'exact' | 'building';

export interface PublicMapProperties {
  slug: string;
  title: string;
  startsAt: string;
  endsAt: string;
  status: PublicStatus;
  categorySlug: string | null;
  imageThumb: string | null;
  venueName: string | null;
  precision: VenuePrecision;
}

export interface PublicMapFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: PublicMapProperties;
}

export interface PublicMapCollection {
  type: 'FeatureCollection';
  generatedAt: string;
  truncated: boolean;
  features: PublicMapFeature[];
}

export interface PublicCampusProperties {
  buildingNo: string;
  name: string;
  approx: boolean;
  count: number;
}

export interface PublicCampusFeature {
  type: 'Feature';
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown };
  properties: PublicCampusProperties;
}

export interface PublicCampusCollection {
  type: 'FeatureCollection';
  attribution?: string;
  features: PublicCampusFeature[];
}

export interface MapQuery {
  past?: boolean;
  from?: string;
  to?: string;
  category?: readonly string[];
  limit?: number;
}

export interface CampusRange {
  from?: string;
  to?: string;
}
