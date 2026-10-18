import { convertToParamMap } from '@angular/router';
import {
  NO_FILTERS,
  activeFilterCount,
  filtersFromParams,
  filtersToParams,
  filtersToQuery,
  rangeDates,
} from './pipeline-filters';

describe('pipeline filters', () => {
  it('round-trips through the URL parameters and drops empty values', () => {
    const filters = {
      q: 'kino',
      organization: 'fsi',
      category: 'film',
      range: 'month' as const,
      mine: true,
      view: 'archived' as const,
    };
    const params = filtersToParams(filters);
    expect(params).toEqual({
      q: 'kino',
      org: 'fsi',
      kategorie: 'film',
      zeitraum: 'month',
      meine: '1',
      ansicht: 'archived',
    });
    expect(filtersFromParams(convertToParamMap(params as Record<string, string>))).toEqual(filters);
    expect(filtersToParams(NO_FILTERS)).toEqual({
      q: null,
      org: null,
      kategorie: null,
      zeitraum: null,
      meine: null,
      ansicht: null,
    });
  });

  it('falls back to no filter for unknown values', () => {
    const read = filtersFromParams(
      convertToParamMap({ zeitraum: 'forever', ansicht: 'trash', meine: '0' }),
    );
    expect(read).toEqual(NO_FILTERS);
  });

  it('counts the set filters but not the view', () => {
    expect(activeFilterCount(NO_FILTERS)).toBe(0);
    expect(activeFilterCount({ ...NO_FILTERS, q: 'a', mine: true, view: 'withdrawn' })).toBe(2);
  });

  it('computes the local dates of each period', () => {
    const wed = new Date(2026, 10, 4);
    expect(rangeDates('week', wed)).toEqual({ from: '2026-11-02', to: '2026-11-08' });
    expect(rangeDates('month', wed)).toEqual({ from: '2026-11-01', to: '2026-11-30' });
    expect(rangeDates('next30', wed)).toEqual({ from: '2026-11-04', to: '2026-12-04' });
    expect(rangeDates('past', wed)).toEqual({ to: '2026-11-03' });
    expect(rangeDates('', wed)).toEqual({});
  });

  it('builds the query: the view archived or withdrawn becomes the one state', () => {
    const today = new Date(2026, 10, 4);
    expect(
      filtersToQuery(
        { ...NO_FILTERS, q: 'x', organization: 'fsi', mine: true, range: 'past' },
        today,
      ),
    ).toEqual({
      q: 'x',
      organization: 'fsi',
      category: undefined,
      mine: true,
      to: '2026-11-03',
    });
    expect(filtersToQuery({ ...NO_FILTERS, view: 'withdrawn' }, today).state).toEqual([
      'withdrawn',
    ]);
  });
});
