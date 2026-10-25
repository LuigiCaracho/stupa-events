/** Great-circle distance between two points, for the client-side "near me" ordering. */
import type { MapPin } from './map.models';

const EARTH_RADIUS_KM = 6371.0088;
const rad = (deg: number): number => (deg * Math.PI) / 180;

export function distanceKm(a: MapPin, b: MapPin): number {
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** `850 m` below one kilometre, else one decimal (`2,4 km`); `localeTag` is an `Intl` tag. */
export function formatDistance(km: number, localeTag: string): string {
  if (km < 1) return `${Math.round(km * 10) * 100} m`;
  return `${new Intl.NumberFormat(localeTag, { maximumFractionDigits: 1 }).format(km)} km`;
}
