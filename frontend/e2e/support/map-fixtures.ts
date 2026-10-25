/**
 * Fixtures of the map specs: 30 events at six places (12 at one place) for the world map, three buildings of the campus
 * with the count of building 9, and the route mocks that serve them. The backend routes are covered by the backend
 * tests; here the browser side is the subject, with data it can predict.
 */
import type { BrowserContext, Page, Route } from '@playwright/test';

export interface Place {
  key: string;
  venue: string;
  lon: number;
  lat: number;
  events: number;
}

/** Centre (9.2, 48.495) is the middle of the bounds, so the map centres on the big cluster. */
export const PLACES: readonly Place[] = [
  { key: 'kino', venue: 'Kinosaal 9-133', lon: 9.2, lat: 48.495, events: 12 },
  { key: 'west', venue: 'Maker Space 9-229', lon: 9.1965, lat: 48.495, events: 4 },
  { key: 'east', venue: 'FSI 9-U09', lon: 9.2035, lat: 48.495, events: 4 },
  { key: 'aula', venue: 'Aula', lon: 9.17, lat: 48.48, events: 3 },
  { key: 'nord', venue: 'Mensa', lon: 9.23, lat: 48.51, events: 3 },
  { key: 'foyer', venue: 'Foyer', lon: 9.17, lat: 48.51, events: 4 },
];

export const NEAR_ME = { latitude: 48.4829, longitude: 9.1873 };

const day = (n: number): string => `2026-12-${String(n).padStart(2, '0')}`;

export function mapCollection(): object {
  let n = 0;
  const features = PLACES.flatMap((place) =>
    Array.from({ length: place.events }, (_, i) => {
      n += 1;
      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [place.lon, place.lat] },
        properties: {
          slug: `${place.key}-${i + 1}`,
          title: `${place.venue} Abend ${i + 1}`,
          startsAt: `${day(1 + (n % 28))}T18:00:00Z`,
          endsAt: `${day(1 + (n % 28))}T20:00:00Z`,
          status: 'scheduled',
          categorySlug: null,
          imageThumb: null,
          venueName: place.venue,
          precision: 'exact',
        },
      };
    }),
  );
  return {
    type: 'FeatureCollection',
    generatedAt: new Date().toISOString(),
    truncated: false,
    features,
  };
}

const square = (lon: number, lat: number, half = 0.0003): number[][][] => [
  [
    [lon - half, lat - half],
    [lon + half, lat - half],
    [lon + half, lat + half],
    [lon - half, lat + half],
    [lon - half, lat - half],
  ],
];

const BUILDINGS = [
  { buildingNo: '9', name: 'Gebäude 9', approx: false, count: 3, at: [9.1873, 48.4829] },
  { buildingNo: '2', name: 'Gebäude 2', approx: false, count: 0, at: [9.1888, 48.4833] },
  { buildingNo: '17', name: 'Gebäude 17', approx: true, count: 1, at: [9.1861, 48.4822] },
];

export function campusCollection(): object {
  return {
    type: 'FeatureCollection',
    features: BUILDINGS.map(({ at, ...properties }) => ({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: square(at[0], at[1]) },
      properties,
    })),
  };
}

const card = (slug: string, title: string, n: number): object => ({
  slug,
  title,
  summary: null,
  startsAt: `${day(n)}T17:00:00Z`,
  endsAt: `${day(n)}T19:00:00Z`,
  allDay: false,
  startsOn: null,
  endsOn: null,
  tzid: 'Europe/Berlin',
  status: 'scheduled',
  statusReason: null,
  organization: { slug: 'stupa', name: 'STUPA', short: 'STUPA' },
  venueName: null,
  categories: [],
  image: null,
  path: `/e/${slug}`,
});

export const BUILDING_9_EVENTS = [
  card('kino-9', 'Kino im Kinosaal', 3),
  card('maker-9', 'Maker Space Treff', 4),
  card('fsi-9', 'FSI Frühstück', 5),
];

const json = (route: Route, body: object): Promise<void> =>
  route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });

/**
 * Serves the world and campus answers; the URL of the request is recorded in `seen`. Pass the context, not the page,
 * when a service worker is active: requests of the worker bypass `page.route`.
 */
export async function mockMapApi(
  page: Page | BrowserContext,
  seen: string[] = [],
): Promise<string[]> {
  await page.route('**/api/public/map/events**', (route) => {
    seen.push(route.request().url());
    return json(route, mapCollection());
  });
  await page.route('**/api/public/campus/buildings**', (route) => {
    seen.push(route.request().url());
    return json(route, campusCollection());
  });
  await page.route('**/api/public/campus/events**', (route) => {
    seen.push(route.request().url());
    return json(route, { items: BUILDING_9_EVENTS, nextCursor: null, total: 3, facets: null });
  });
  return seen;
}
