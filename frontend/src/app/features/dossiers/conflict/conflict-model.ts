/**
 * The three-way view of an edit conflict (E21): for every field the person changed, the value of the base revision, the
 * person's own value and the value in the current version. Pure functions; the dialog renders the rows.
 */
import type { ConfigDiffData } from '@stupa-makers/ui-kit';
import { formatEventTime } from '../api/event-time';
import type { EventDto, EventFields } from '../api/event.models';

export type Choice = 'mine' | 'theirs';

export interface ConflictRow {
  field: keyof EventFields;
  base: unknown;
  mine: unknown;
  theirs: unknown;
  /** The field changed on both sides: the person must choose. */
  contested: boolean;
}

const READ: Record<keyof EventFields, (e: EventDto) => unknown> = {
  title: (e) => e.title,
  startsAt: (e) => e.startsAt,
  endsAt: (e) => e.endsAt,
  allDay: (e) => e.allDay,
  venueId: (e) => e.venueId ?? null,
  venueText: (e) => e.venueText,
  primaryCategoryId: (e) => e.primaryCategory?.id ?? null,
  ticketUrl: (e) => e.ticketUrl ?? null,
  websiteUrl: (e) => e.websiteUrl ?? null,
  summary: (e) => e.summary,
  descriptionMd: (e) => e.descriptionMd,
  costText: (e) => e.costText ?? null,
};

const SNAPSHOT_KEY: Record<keyof EventFields, string> = {
  title: 'title',
  startsAt: 'startsAt',
  endsAt: 'endsAt',
  allDay: 'allDay',
  venueId: 'venueId',
  venueText: 'venueText',
  primaryCategoryId: 'primaryCategoryId',
  ticketUrl: 'ticketUrl',
  websiteUrl: 'websiteUrl',
  summary: 'summary',
  descriptionMd: 'descriptionMd',
  costText: 'costText',
};

const norm = (v: unknown): unknown => (v === undefined || v === '' ? null : v);
const equal = (a: unknown, b: unknown): boolean => norm(a) === norm(b);

/** The rows of the conflict: every field of `mine`, plus every field the current version changed against the base. */
export function conflictRows(
  mine: EventFields,
  current: EventDto,
  baseSnapshot: Record<string, unknown> | null,
): ConflictRow[] {
  const keys = Object.keys(READ) as (keyof EventFields)[];
  return keys
    .map((field) => {
      const theirs = READ[field](current);
      const key = SNAPSHOT_KEY[field];
      const base = baseSnapshot && key in baseSnapshot ? baseSnapshot[key] : undefined;
      const own = field in mine ? mine[field] : theirs;
      const changedByMe = field in mine && !equal(own, base ?? theirs);
      const changedByThem = base !== undefined && !equal(theirs, base);
      return {
        field,
        base,
        mine: own,
        theirs,
        contested: changedByMe && changedByThem && !equal(own, theirs),
      };
    })
    .filter((row) => row.field in mine || (row.base !== undefined && !equal(row.theirs, row.base)));
}

/** The server changes since the base as a diff for the kit component (base to current, only changed fields). */
export function serverDiff(rows: readonly ConflictRow[]): ConfigDiffData {
  return {
    added: [],
    removed: [],
    changed: rows
      .filter((r) => r.base !== undefined && !equal(r.theirs, r.base))
      .map((r) => ({ key: r.field, old: r.base, new: r.theirs })),
  };
}

/** The fields to send with `PATCH`: own values of the fields the person keeps (default: own where not contested). */
export function chosenFields(
  rows: readonly ConflictRow[],
  choices: Readonly<Record<string, Choice>>,
  mine: EventFields,
): EventFields {
  const out: Record<string, unknown> = {};
  for (const row of rows) {
    if (!(row.field in mine)) continue;
    const choice = choices[row.field] ?? (row.contested ? 'theirs' : 'mine');
    if (choice === 'mine' && !equal(row.mine, row.theirs)) out[row.field] = mine[row.field];
  }
  return out as EventFields;
}

export interface Lookups {
  tzid: string;
  venues: readonly { id: string; name: string }[];
  categories: readonly { id: string; name: string }[];
  empty: string;
}

/** A value as the dialog shows it: times in the zone of the event, ids by name, nothing as "leer". */
export function formatValue(field: keyof EventFields, value: unknown, look: Lookups): string {
  if (value === null || value === undefined || value === '') return look.empty;
  if (field === 'startsAt' || field === 'endsAt') return formatEventTime(String(value), look.tzid);
  if (field === 'venueId') return look.venues.find((v) => v.id === value)?.name ?? String(value);
  if (field === 'primaryCategoryId')
    return look.categories.find((c) => c.id === value)?.name ?? String(value);
  return String(value);
}
