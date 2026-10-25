/** Pure rules of the venue pin sheet: when the address search is allowed, what an answer or a failure means. */
import type { Problem } from '@core/api/models';
import type { TranslationKey } from '@core/i18n/translations';
import type { AdminVenue, VenueGeocode } from '../../api/admin.models';

type Searchable = Pick<AdminVenue, 'id' | 'isPrivate' | 'address' | 'city'>;

/** `null` when the stored venue may be searched, else the reason as a catalog key. */
export function searchBlock(venue: Searchable | null): TranslationKey | null {
  if (!venue || venue.id === 'new') return 'admin.pin.saveFirst';
  if (venue.isPrivate) return 'admin.pin.private';
  if (!venue.address?.trim() || !venue.city?.trim()) return 'admin.pin.noAddress';
  return null;
}

export function geocodeError(problem: Problem): TranslationKey {
  if (problem.status === 429) return 'admin.pin.rate';
  if (problem.status === 503 && problem.code === 'geocode_disabled') return 'admin.pin.disabled';
  if (problem.code === 'venue_private') return 'admin.pin.private';
  if (problem.code === 'address_incomplete') return 'admin.pin.noAddress';
  return 'admin.pin.failed';
}

export const toNumber = (value: number | string | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export function suggestion(answer: VenueGeocode): { lat: number; lon: number } | null {
  const lat = toNumber(answer.lat);
  const lon = toNumber(answer.lon);
  return answer.found && lat !== null && lon !== null ? { lat, lon } : null;
}
