/**
 * The filters of the public search as they live in the URL (`/suche?q=&category=&organization=&from=&to=&past=`),
 * the API query built from them and the time chips ("heute", "Wochenende", "7 Tage", "Monat") that only compute
 * `from` and `to` in Berlin days on the client (B1 contract 2.2.5).
 */
import type { Params, ParamMap } from '@angular/router';
import { addDays, firstOfMonth, startOfWeek } from '@shared/ui/calendar-grid/calendar-grid.util';
import type { TranslationKey } from '@core/i18n/translations';
import type { PublicSearchQuery } from './public.models';

export interface SearchFilters {
  q: string;
  category: readonly string[];
  organization: readonly string[];
  from: string;
  to: string;
  past: boolean;
}

export const EMPTY_FILTERS: SearchFilters = {
  q: '',
  category: [],
  organization: [],
  from: '',
  to: '',
  past: false,
};

export const QUERY_MAX_LENGTH = 100;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const SLUG_LIMIT = 10;

export type TimeChip = 'today' | 'weekend' | 'week' | 'month';
export const TIME_CHIPS: readonly TimeChip[] = ['today', 'weekend', 'week', 'month'];

export const TIME_CHIP_KEYS: Record<TimeChip, TranslationKey> = {
  today: 'public.time.today',
  weekend: 'public.time.weekend',
  week: 'public.time.week',
  month: 'public.time.month',
};

const slugs = (values: string[]): string[] =>
  [...new Set(values.filter((v) => /^[a-z0-9-]{1,80}$/.test(v)))].slice(0, SLUG_LIMIT);

export function parseFilters(params: ParamMap): SearchFilters {
  const day = (key: string): string => {
    const v = params.get(key) ?? '';
    return DAY.test(v) ? v : '';
  };
  return {
    q: (params.get('q') ?? '').slice(0, QUERY_MAX_LENGTH),
    category: slugs(params.getAll('category')),
    organization: slugs(params.getAll('organization')),
    from: day('from'),
    to: day('to'),
    past: params.get('past') === '1',
  };
}

/** The query params of the URL; empty values are left out so the URL stays short and shareable. */
export function toQueryParams(f: SearchFilters): Params {
  return {
    q: f.q.trim() || null,
    category: f.category.length > 0 ? f.category : null,
    organization: f.organization.length > 0 ? f.organization : null,
    from: f.from || null,
    to: f.to || null,
    past: f.past ? '1' : null,
  };
}

export function toApiQuery(f: SearchFilters, cursor: string | null = null): PublicSearchQuery {
  return {
    q: f.q.trim(),
    category: f.category,
    organization: f.organization,
    from: f.from,
    to: f.to,
    past: f.past,
    cursor,
  };
}

/** The number on the "Filter (n)" button: every set filter group counts once, the text not at all. */
export function activeCount(f: SearchFilters): number {
  return (
    Number(f.category.length > 0) +
    Number(f.organization.length > 0) +
    Number(f.from !== '' || f.to !== '')
  );
}

export const hasAnyFilter = (f: SearchFilters): boolean => f.q.trim() !== '' || activeCount(f) > 0;

/** The day range a time chip stands for, counted from `today` (a Berlin day key). */
export function chipRange(chip: TimeChip, today: string): { from: string; to: string } {
  if (chip === 'today') return { from: today, to: today };
  if (chip === 'week') return { from: today, to: addDays(today, 6) };
  if (chip === 'weekend') {
    const saturday = addDays(startOfWeek(today), 5);
    const sunday = addDays(saturday, 1);
    return { from: today > saturday ? today : saturday, to: sunday };
  }
  const next = addDays(firstOfMonth(addDays(firstOfMonth(today), 40)), -1);
  return { from: today, to: next };
}

/** The chip whose range is exactly the one of the filters, or `null`. */
export function activeChip(f: SearchFilters, today: string): TimeChip | null {
  if (!f.from || !f.to) return null;
  return (
    TIME_CHIPS.find((c) => {
      const r = chipRange(c, today);
      return r.from === f.from && r.to === f.to;
    }) ?? null
  );
}
