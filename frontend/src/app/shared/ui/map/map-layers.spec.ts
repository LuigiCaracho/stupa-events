import { readMapColors } from './map-theme';
import {
  CAMPUS_STEPS,
  campusLayers,
  campusLegend,
  eventsLayers,
  selectionFilter,
} from './map-layers';
import { collectionBounds } from './map-bounds';
import { distanceKm, formatDistance } from './geo-distance';
import { EMPTY_COLLECTION, type GeoCollection } from './map.models';

const colors = readMapColors(document.body);

describe('map layers', () => {
  it('clusters on one source and filters points by cluster membership', () => {
    const layers = eventsLayers(colors);
    expect(layers.map((l) => l.id)).toEqual([
      'ev-clusters',
      'ev-cluster-count',
      'ev-points',
      'ev-selected',
    ]);
    expect(layers[0]).toMatchObject({ filter: ['has', 'point_count'] });
    expect(layers[2]).toMatchObject({ filter: ['!', ['has', 'point_count']] });
  });

  it('shows the building number and the count in the campus label', () => {
    const label = campusLayers(colors).find((l) => l.id === 'ev-campus-label');
    expect(JSON.stringify(label?.layout)).toContain('buildingNo');
    expect(JSON.stringify(label?.layout)).toContain('count');
  });

  it('keeps the legend steps in step with the fill expression', () => {
    const legend = campusLegend();
    expect(legend.map((l) => l.from)).toEqual([...CAMPUS_STEPS]);
    expect(legend.at(-1)?.to).toBeNull();
  });

  it('selects no event by default', () => {
    expect(selectionFilter(null)).toEqual(['==', ['get', 'slug'], '']);
    expect(selectionFilter('a')).toEqual(['==', ['get', 'slug'], 'a']);
  });

  it('falls back to token defaults without a stylesheet', () => {
    expect(colors.accent).toMatch(/^#/);
    expect(colors.levels).toHaveLength(3);
  });
});

describe('collectionBounds', () => {
  const point = (lon: number, lat: number) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point', coordinates: [lon, lat] },
    properties: null,
  });

  it('is null for an empty collection', () => {
    expect(collectionBounds(EMPTY_COLLECTION)).toBeNull();
  });

  it('spans points and polygons', () => {
    const data: GeoCollection = {
      type: 'FeatureCollection',
      features: [
        point(9.1, 48.4),
        {
          type: 'Feature',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [9.3, 48.5],
                [9.4, 48.6],
                [9.3, 48.5],
              ],
            ],
          },
          properties: null,
        },
      ],
    };
    expect(collectionBounds(data)).toEqual([9.1, 48.4, 9.4, 48.6]);
  });
});

describe('distance', () => {
  it('measures Reutlingen to Stuttgart at about 30 km', () => {
    const km = distanceKm({ lat: 48.4914, lon: 9.2043 }, { lat: 48.7758, lon: 9.1829 });
    expect(km).toBeGreaterThan(30);
    expect(km).toBeLessThan(33);
  });

  it('formats short and long distances', () => {
    expect(formatDistance(0.85, 'de-DE')).toBe('900 m');
    expect(formatDistance(2.44, 'de-DE')).toBe('2,4 km');
  });
});
