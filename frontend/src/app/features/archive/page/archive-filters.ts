/**
 * The filters of the archive page as one value and their form in the URL (`q, scope, status, org, jahr, kategorie,
 * format`). The default is the archive itself: `status` absent means `archived`, `status=alle` means every state.
 */
import type { ParamMap, Params } from '@angular/router';
import type { SearchQuery, SearchScope } from '../model/archive.models';

export interface ArchiveFilters {
  q: string;
  scope: SearchScope;
  state: readonly string[];
  org: string;
  year: string;
  category: string;
  format: string;
}

export const NO_ARCHIVE_FILTERS: ArchiveFilters = {
  q: '',
  scope: 'events',
  state: ['archived'],
  org: '',
  year: '',
  category: '',
  format: '',
};

const SCOPES: readonly SearchScope[] = ['events', 'documents', 'formats'];
export const MAX_QUERY = 100;
export const MIN_QUERY = 2;

export function archiveFromParams(params: ParamMap): ArchiveFilters {
  const scope = params.get('scope') as SearchScope;
  const status = params.getAll('status');
  return {
    q: params.get('q') ?? '',
    scope: SCOPES.includes(scope) ? scope : 'events',
    state: status.length === 0 ? ['archived'] : status.includes('alle') ? [] : status,
    org: params.get('org') ?? '',
    year: params.get('jahr') ?? '',
    category: params.get('kategorie') ?? '',
    format: params.get('format') ?? '',
  };
}

export function archiveToParams(f: ArchiveFilters): Params {
  const isDefault = f.state.length === 1 && f.state[0] === 'archived';
  return {
    q: f.q || null,
    scope: f.scope === 'events' ? null : f.scope,
    status: isDefault ? null : f.state.length === 0 ? 'alle' : f.state,
    org: f.org || null,
    jahr: f.year || null,
    kategorie: f.category || null,
    format: f.format || null,
  };
}

export const searchable = (f: ArchiveFilters): boolean => f.q.trim().length >= MIN_QUERY;

export function archiveToQuery(f: ArchiveFilters, offset = 0): SearchQuery {
  return {
    q: f.q.trim(),
    scope: f.scope,
    ...(f.scope === 'events' && f.state.length > 0 && { state: f.state }),
    org: f.org || undefined,
    year: f.year || undefined,
    category: f.category || undefined,
    format: f.format || undefined,
    offset: offset || undefined,
  };
}

export function activeFacets(f: ArchiveFilters): number {
  const stateChanged = f.scope === 'events' && !(f.state.length === 1 && f.state[0] === 'archived');
  return [f.org, f.year, f.category, f.format].filter(Boolean).length + (stateChanged ? 1 : 0);
}
