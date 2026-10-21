import { convertToParamMap } from '@angular/router';
import {
  NO_FILTERS,
  activeFilterCount,
  filtersFromParams,
  filtersToParams,
  filtersToQuery,
  statesOf,
} from './event-filters';

describe('event filters', () => {
  it('round-trips through the URL parameters and drops empty values', () => {
    const filters = {
      q: 'kino',
      organization: 'fsi',
      category: 'film',
      state: 'cancelled' as const,
      year: '2026',
      mine: true,
      view: 'calendar' as const,
    };
    const params = filtersToParams(filters);
    expect(params).toEqual({
      q: 'kino',
      org: 'fsi',
      kategorie: 'film',
      zustand: 'cancelled',
      jahr: '2026',
      meine: '1',
      ansicht: 'kalender',
    });
    expect(filtersFromParams(convertToParamMap(params as Record<string, string>))).toEqual(filters);
    expect(Object.values(filtersToParams(NO_FILTERS)).every((v) => v === null)).toBe(true);
  });

  it('falls back to no filter for unknown values', () => {
    const read = filtersFromParams(
      convertToParamMap({ zustand: 'live', jahr: 'bald', ansicht: 'board', meine: '0' }),
    );
    expect(read).toEqual(NO_FILTERS);
  });

  it('counts the set filters but not the view', () => {
    expect(activeFilterCount(NO_FILTERS)).toBe(0);
    expect(activeFilterCount({ ...NO_FILTERS, q: 'a', mine: true, view: 'calendar' })).toBe(2);
  });

  it('builds the query: the year becomes a range, "abgesagt" asks for published events', () => {
    expect(
      filtersToQuery({ ...NO_FILTERS, q: 'x', organization: 'fsi', mine: true, year: '2026' }),
    ).toEqual({
      q: 'x',
      organization: 'fsi',
      category: undefined,
      mine: true,
      from: '2026-01-01',
      to: '2026-12-31',
      state: ['draft', 'published'],
    });
    expect(filtersToQuery({ ...NO_FILTERS, state: 'cancelled' }).state).toEqual(['published']);
    expect(filtersToQuery({ ...NO_FILTERS, state: 'draft' }).state).toEqual(['draft']);
    expect(filtersToQuery(NO_FILTERS).state).toEqual(['draft', 'published']);
    expect(filtersToQuery({ ...NO_FILTERS, state: 'archived' })).toMatchObject({
      state: ['archived'],
      sort: '-startsAt',
    });
    expect(statesOf('')).toEqual([]);
  });
});
