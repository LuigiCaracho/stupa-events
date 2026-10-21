import { convertToParamMap } from '@angular/router';
import {
  NO_ARCHIVE_FILTERS,
  activeFacets,
  archiveFromParams,
  archiveToParams,
  archiveToQuery,
  searchable,
} from './archive-filters';

describe('archive filters', () => {
  it('defaults to the archive and writes nothing to the URL for the default', () => {
    expect(archiveFromParams(convertToParamMap({}))).toEqual(NO_ARCHIVE_FILTERS);
    expect(archiveToParams(NO_ARCHIVE_FILTERS)).toEqual({
      q: null, scope: null, status: null, org: null, jahr: null, kategorie: null, format: null,
    });
  });

  it('reads and writes states, "alle" and the scope', () => {
    const f = archiveFromParams(convertToParamMap({ q: 'kino', scope: 'documents', status: ['live', 'followup'] }));
    expect(f).toMatchObject({ q: 'kino', scope: 'documents', state: ['live', 'followup'] });
    expect(archiveToParams(f)).toMatchObject({ scope: 'documents', status: ['live', 'followup'] });
    const all = archiveFromParams(convertToParamMap({ status: 'alle' }));
    expect(all.state).toEqual([]);
    expect(archiveToParams(all)['status']).toBe('alle');
  });

  it('falls back to events for an unknown scope', () => {
    expect(archiveFromParams(convertToParamMap({ scope: 'x' })).scope).toBe('events');
  });

  it('searches from two characters and sends the state filter only for dossiers', () => {
    expect(searchable({ ...NO_ARCHIVE_FILTERS, q: ' k ' })).toBe(false);
    expect(searchable({ ...NO_ARCHIVE_FILTERS, q: 'ki' })).toBe(true);
    expect(archiveToQuery({ ...NO_ARCHIVE_FILTERS, q: ' kino ', year: '2026' }, 20)).toEqual({
      q: 'kino', scope: 'events', state: ['archived'], org: undefined, year: '2026',
      category: undefined, format: undefined, offset: 20,
    });
    expect(archiveToQuery({ ...NO_ARCHIVE_FILTERS, q: 'kino', scope: 'formats' }).state).toBeUndefined();
  });

  it('counts the active facets', () => {
    expect(activeFacets(NO_ARCHIVE_FILTERS)).toBe(0);
    expect(activeFacets({ ...NO_ARCHIVE_FILTERS, org: 'fsi', state: [] })).toBe(2);
  });
});
