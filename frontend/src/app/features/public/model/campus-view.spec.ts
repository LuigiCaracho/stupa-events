import { asCampusGeo, campusRange, campusRows, campusTotal, legendRanges } from './campus-view';
import type { PublicCampusCollection } from './map.models';

const building = (buildingNo: string, count: number, approx = false) => ({
  type: 'Feature' as const,
  geometry: { type: 'Polygon' as const, coordinates: [] },
  properties: { buildingNo, name: `Gebäude ${buildingNo}`, approx, count },
});

const data: PublicCampusCollection = {
  type: 'FeatureCollection',
  features: [building('10', 0), building('9', 3), building('2', 0), building('17', 1, true)],
};

describe('campus view', () => {
  it('uses the Berlin day, not the UTC day', () => {
    const lateEvening = new Date('2026-10-24T22:30:00Z');
    expect(campusRange('today', lateEvening)).toEqual({ from: '2026-10-25', to: '2026-10-25' });
  });

  it('spans seven days for the week, across a month change', () => {
    expect(campusRange('week', new Date('2026-10-28T10:00:00Z'))).toEqual({
      from: '2026-10-28',
      to: '2026-11-03',
    });
  });

  it('lists buildings with events first, then by number', () => {
    expect(campusRows(data).map((r) => r.buildingNo)).toEqual(['9', '17', '2', '10']);
  });

  it('sums the counts', () => {
    expect(campusTotal(data)).toBe(4);
    expect(campusTotal(undefined)).toBe(0);
  });

  it('describes four levels that end open', () => {
    const ranges = legendRanges();
    expect(ranges.map((r) => r.level)).toEqual([0, 1, 2, 3]);
    expect(ranges.at(-1)?.to).toBeNull();
  });

  it('hands the polygons to the map', () => {
    expect(asCampusGeo(data).features).toHaveLength(4);
  });
});
