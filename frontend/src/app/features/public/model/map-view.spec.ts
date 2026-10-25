import { asGeo, mapRows, yearChoices, yearRange } from './map-view';
import type { PublicMapCollection, PublicMapFeature } from './map.models';

const feature = (slug: string, lon: number, lat: number, startsAt: string): PublicMapFeature => ({
  type: 'Feature',
  geometry: { type: 'Point', coordinates: [lon, lat] },
  properties: {
    slug,
    title: slug,
    startsAt,
    endsAt: startsAt,
    status: 'scheduled',
    categorySlug: null,
    imageThumb: null,
    venueName: null,
    precision: 'exact',
  },
});

const collection: PublicMapCollection = {
  type: 'FeatureCollection',
  generatedAt: '2026-10-25T10:00:00Z',
  truncated: false,
  features: [
    feature('davos', 9.84, 46.8, '2026-01-10T08:00:00Z'),
    feature('campus', 9.17, 48.48, '2026-11-02T08:00:00Z'),
    feature('rust', 7.72, 48.27, '2026-12-05T08:00:00Z'),
  ],
};
const slugs = (rows: { feature: PublicMapFeature }[]) => rows.map((r) => r.feature.properties.slug);

describe('map view', () => {
  it('orders upcoming by date and past by date descending', () => {
    expect(slugs(mapRows(collection, null, false, null))).toEqual(['davos', 'campus', 'rust']);
    expect(slugs(mapRows(collection, null, true, null))).toEqual(['rust', 'campus', 'davos']);
  });

  it('orders by distance once a position is known and reports kilometres', () => {
    const rows = mapRows(collection, { lat: 48.4829, lon: 9.1873 }, false, null);
    expect(slugs(rows)).toEqual(['campus', 'rust', 'davos']);
    expect(rows[0].km).toBeLessThan(2);
  });

  it('keeps only the slugs of a selected cluster', () => {
    expect(slugs(mapRows(collection, null, false, ['rust']))).toEqual(['rust']);
  });

  it('turns a year into a day range and offers the last five years', () => {
    expect(yearRange(2025)).toEqual({ from: '2025-01-01', to: '2025-12-31' });
    expect(yearRange(null)).toEqual({});
    expect(yearChoices(2026)).toEqual([2026, 2025, 2024, 2023, 2022]);
  });

  it('hands the features to the map unchanged', () => {
    expect(asGeo(collection).features).toHaveLength(3);
    expect(asGeo(undefined).features).toEqual([]);
  });
});
