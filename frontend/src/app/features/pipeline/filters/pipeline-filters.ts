/**
 * The filters of the board and the dossier list as one value: how they travel in the URL (so a reload and
 * "back" keep them) and how they become the query of `GET /api/events`. Pure functions, no state.
 */
import type { ParamMap, Params } from '@angular/router';
import type { EventQuery } from '../../dossiers/api/board.models';

export type RangePreset = '' | 'week' | 'month' | 'next30' | 'past';
export type BoardView = 'active' | 'archived' | 'withdrawn';

export interface PipelineFilters {
  q: string;
  organization: string;
  category: string;
  range: RangePreset;
  mine: boolean;
  view: BoardView;
}

export const NO_FILTERS: PipelineFilters = {
  q: '',
  organization: '',
  category: '',
  range: '',
  mine: false,
  view: 'active',
};

const RANGES: readonly RangePreset[] = ['week', 'month', 'next30', 'past'];
const VIEWS: readonly BoardView[] = ['archived', 'withdrawn'];

/** Reads the filters from the query parameters; unknown values fall back to "no filter". */
export function filtersFromParams(params: ParamMap): PipelineFilters {
  const range = params.get('zeitraum') as RangePreset;
  const view = params.get('ansicht') as BoardView;
  return {
    q: params.get('q') ?? '',
    organization: params.get('org') ?? '',
    category: params.get('kategorie') ?? '',
    range: RANGES.includes(range) ? range : '',
    mine: params.get('meine') === '1',
    view: VIEWS.includes(view) ? view : 'active',
  };
}

/** The query parameters of the filters; empty values are dropped so the URL stays short. */
export function filtersToParams(filters: PipelineFilters): Params {
  return {
    q: filters.q || null,
    org: filters.organization || null,
    kategorie: filters.category || null,
    zeitraum: filters.range || null,
    meine: filters.mine ? '1' : null,
    ansicht: filters.view === 'active' ? null : filters.view,
  };
}

/** How many filters are set, for the reset button; the view is not a filter. */
export function activeFilterCount(filters: PipelineFilters): number {
  return (
    [filters.q, filters.organization, filters.category, filters.range].filter(Boolean).length +
    (filters.mine ? 1 : 0)
  );
}

const pad = (n: number): string => String(n).padStart(2, '0');
const day = (d: Date): string => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const shift = (d: Date, days: number): Date =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate() + days);

/** The local dates `from` and `to` of a preset, relative to `today`. */
export function rangeDates(range: RangePreset, today: Date): { from?: string; to?: string } {
  switch (range) {
    case 'week': {
      const monday = shift(today, -((today.getDay() + 6) % 7));
      return { from: day(monday), to: day(shift(monday, 6)) };
    }
    case 'month':
      return {
        from: day(new Date(today.getFullYear(), today.getMonth(), 1)),
        to: day(new Date(today.getFullYear(), today.getMonth() + 1, 0)),
      };
    case 'next30':
      return { from: day(today), to: day(shift(today, 30)) };
    case 'past':
      return { to: day(shift(today, -1)) };
    default:
      return {};
  }
}

/** The query of the board or the list for the filters. */
export function filtersToQuery(filters: PipelineFilters, today: Date = new Date()): EventQuery {
  return {
    q: filters.q || undefined,
    organization: filters.organization || undefined,
    category: filters.category || undefined,
    mine: filters.mine || undefined,
    ...rangeDates(filters.range, today),
    ...(filters.view === 'active' ? {} : { state: [filters.view] }),
  };
}
