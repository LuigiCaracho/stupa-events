/** The filters of the library page and their form in the URL (`q, art, kategorie, org, jahr`). */
import type { ParamMap, Params } from '@angular/router';
import type { LibraryQuery } from '../model/library.models';

export interface LibraryFilters {
  q: string;
  kind: string;
  category: string;
  organization: string;
  year: string;
}

export const NO_LIBRARY_FILTERS: LibraryFilters = {
  q: '',
  kind: '',
  category: '',
  organization: '',
  year: '',
};

export function libraryFromParams(params: ParamMap): LibraryFilters {
  return {
    q: params.get('q') ?? '',
    kind: params.get('art') ?? '',
    category: params.get('kategorie') ?? '',
    organization: params.get('org') ?? '',
    year: params.get('jahr') ?? '',
  };
}

export function libraryToParams(f: LibraryFilters): Params {
  return {
    q: f.q || null,
    art: f.kind || null,
    kategorie: f.category || null,
    org: f.organization || null,
    jahr: f.year || null,
  };
}

export function libraryToQuery(f: LibraryFilters, offset = 0): LibraryQuery {
  return {
    q: f.q.trim() || undefined,
    kind: f.kind || undefined,
    category: f.category || undefined,
    organization: f.organization || undefined,
    year: f.year || undefined,
    offset: offset || undefined,
    limit: 50,
  };
}

export const activeLibraryFilters = (f: LibraryFilters): number =>
  [f.q, f.kind, f.category, f.organization, f.year].filter(Boolean).length;
