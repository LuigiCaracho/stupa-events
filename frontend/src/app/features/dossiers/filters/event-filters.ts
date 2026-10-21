/**
 * The filters of the event list and its calendar as one value: how they travel in the URL (so a reload and "back"
 * keep them, including the switch Liste | Kalender) and how they become the query of `GET /api/events`. Pure functions.
 */
import type { ParamMap, Params } from '@angular/router';
import type { UrlStateCodec } from '@shared/url-state';
import type { EventState } from '@shared/status-kind.util';
import type { EventQuery } from '../api/card.models';

export type StateChip = '' | EventState | 'cancelled';
export type ListView = 'list' | 'calendar';

export interface EventFilters {
  q: string;
  organization: string;
  category: string;
  state: StateChip;
  year: string;
  mine: boolean;
  view: ListView;
}

export const NO_FILTERS: EventFilters = {
  q: '',
  organization: '',
  category: '',
  state: '',
  year: '',
  mine: false,
  view: 'list',
};

export const STATE_CHIPS: readonly Exclude<StateChip, ''>[] = [
  'draft',
  'published',
  'archived',
  'cancelled',
];

const YEAR = /^\d{4}$/;

export function filtersFromParams(params: ParamMap): EventFilters {
  const state = params.get('zustand') as StateChip;
  const year = params.get('jahr') ?? '';
  return {
    q: params.get('q') ?? '',
    organization: params.get('org') ?? '',
    category: params.get('kategorie') ?? '',
    state: STATE_CHIPS.includes(state as Exclude<StateChip, ''>) ? state : '',
    year: YEAR.test(year) ? year : '',
    mine: params.get('meine') === '1',
    view: params.get('ansicht') === 'kalender' ? 'calendar' : 'list',
  };
}

export function filtersToParams(filters: EventFilters): Params {
  return {
    q: filters.q || null,
    org: filters.organization || null,
    kategorie: filters.category || null,
    zustand: filters.state || null,
    jahr: filters.year || null,
    meine: filters.mine ? '1' : null,
    ansicht: filters.view === 'calendar' ? 'kalender' : null,
  };
}

/** How many filters are set, for the reset button; the view is not a filter. */
export function activeFilterCount(filters: EventFilters): number {
  return (
    [filters.q, filters.organization, filters.category, filters.state, filters.year].filter(Boolean)
      .length + (filters.mine ? 1 : 0)
  );
}

/** The states the server is asked for: "abgesagt" is a mark on a published event, so it asks for `published`. */
export function statesOf(state: StateChip): EventState[] {
  if (state === '') return [];
  return [state === 'cancelled' ? 'published' : state];
}

const ACTIVE: readonly EventState[] = ['draft', 'published'];

/** The query of the list for the filters; the year becomes the range `from`/`to`, no state chip hides the archive. */
export function filtersToQuery(filters: EventFilters): EventQuery {
  const states = filters.state === '' ? ACTIVE : statesOf(filters.state);
  return {
    q: filters.q || undefined,
    organization: filters.organization || undefined,
    category: filters.category || undefined,
    mine: filters.mine || undefined,
    ...(filters.year ? { from: `${filters.year}-01-01`, to: `${filters.year}-12-31` } : {}),
    state: states,
    ...(filters.state === 'archived' ? { sort: '-startsAt' as const } : {}),
  };
}

export const eventFiltersCodec: UrlStateCodec<EventFilters> = {
  parse: filtersFromParams,
  serialize: filtersToParams,
  typing: (prev, next) => prev.q !== next.q,
};
