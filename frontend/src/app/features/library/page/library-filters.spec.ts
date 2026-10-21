import { convertToParamMap } from '@angular/router';
import {
  NO_LIBRARY_FILTERS,
  activeLibraryFilters,
  libraryFromParams,
  libraryToParams,
  libraryToQuery,
} from './library-filters';

describe('library filters', () => {
  it('reads and writes the German parameter names and drops empty values', () => {
    const f = libraryFromParams(convertToParamMap({ q: 'cafe', art: 'document', kategorie: 'cafe', org: 'makers', jahr: '2025' }));
    expect(f).toEqual({ q: 'cafe', kind: 'document', category: 'cafe', organization: 'makers', year: '2025' });
    expect(libraryToParams(f)).toEqual({ q: 'cafe', art: 'document', kategorie: 'cafe', org: 'makers', jahr: '2025' });
    expect(libraryToParams(NO_LIBRARY_FILTERS)).toEqual({ q: null, art: null, kategorie: null, org: null, jahr: null });
  });

  it('builds the query with a page size and an offset only when set', () => {
    expect(libraryToQuery({ ...NO_LIBRARY_FILTERS, q: ' cafe ' })).toEqual({
      q: 'cafe', kind: undefined, category: undefined, organization: undefined, year: undefined, offset: undefined, limit: 50,
    });
    expect(libraryToQuery(NO_LIBRARY_FILTERS, 50).offset).toBe(50);
  });

  it('counts the active filters', () => {
    expect(activeLibraryFilters(NO_LIBRARY_FILTERS)).toBe(0);
    expect(activeLibraryFilters({ ...NO_LIBRARY_FILTERS, q: 'x', year: '2025' })).toBe(2);
  });
});
