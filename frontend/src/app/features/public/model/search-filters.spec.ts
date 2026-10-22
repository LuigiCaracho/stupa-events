/** Spec for the URL state of the public search and the time chips. */
import { convertToParamMap } from '@angular/router';
import {
  EMPTY_FILTERS,
  QUERY_MAX_LENGTH,
  activeChip,
  activeCount,
  chipRange,
  hasAnyFilter,
  parseFilters,
  toApiQuery,
  toQueryParams,
} from './search-filters';

describe('search filters in the URL', () => {
  it('reads every filter and drops what is not valid', () => {
    const f = parseFilters(
      convertToParamMap({
        q: 'kino',
        category: ['party', 'Bad Slug', 'party'],
        organization: 'fsi',
        from: '2026-10-22',
        to: 'morgen',
        past: '1',
      }),
    );
    expect(f).toEqual({
      q: 'kino',
      category: ['party'],
      organization: ['fsi'],
      from: '2026-10-22',
      to: '',
      past: true,
    });
  });

  it('cuts the text at the length the server accepts', () => {
    const f = parseFilters(convertToParamMap({ q: 'a'.repeat(QUERY_MAX_LENGTH + 20) }));
    expect(f.q).toHaveLength(QUERY_MAX_LENGTH);
  });

  it('writes only set filters back, so an empty search has a bare URL', () => {
    expect(toQueryParams(EMPTY_FILTERS)).toEqual({
      q: null,
      category: null,
      organization: null,
      from: null,
      to: null,
      past: null,
    });
    expect(toQueryParams({ ...EMPTY_FILTERS, category: ['party'], past: true })).toMatchObject({
      category: ['party'],
      past: '1',
    });
  });

  it('builds the API query with the trimmed text and the cursor', () => {
    const q = toApiQuery({ ...EMPTY_FILTERS, q: '  kino ' }, 'abc');
    expect(q).toMatchObject({ q: 'kino', cursor: 'abc' });
  });

  it('counts a filter group once and not the text', () => {
    const f = { ...EMPTY_FILTERS, q: 'x', category: ['a', 'b'], from: '2026-10-01' };
    expect(activeCount(f)).toBe(2);
    expect(hasAnyFilter(EMPTY_FILTERS)).toBe(false);
    expect(hasAnyFilter({ ...EMPTY_FILTERS, q: 'x' })).toBe(true);
  });
});

describe('time chips', () => {
  const THURSDAY = '2026-10-22';

  it('computes the ranges in Berlin days', () => {
    expect(chipRange('today', THURSDAY)).toEqual({ from: THURSDAY, to: THURSDAY });
    expect(chipRange('week', THURSDAY)).toEqual({ from: THURSDAY, to: '2026-10-28' });
    expect(chipRange('weekend', THURSDAY)).toEqual({ from: '2026-10-24', to: '2026-10-25' });
    expect(chipRange('month', THURSDAY)).toEqual({ from: THURSDAY, to: '2026-10-31' });
  });

  it('keeps today inside the weekend on a Sunday', () => {
    expect(chipRange('weekend', '2026-10-25')).toEqual({ from: '2026-10-25', to: '2026-10-25' });
  });

  it('ends the month on its real last day', () => {
    expect(chipRange('month', '2026-02-10').to).toBe('2026-02-28');
    expect(chipRange('month', '2028-02-10').to).toBe('2028-02-29');
  });

  it('finds the chip a range belongs to', () => {
    const f = { ...EMPTY_FILTERS, ...chipRange('week', THURSDAY) };
    expect(activeChip(f, THURSDAY)).toBe('week');
    expect(activeChip({ ...f, to: '2026-11-30' }, THURSDAY)).toBeNull();
  });
});
