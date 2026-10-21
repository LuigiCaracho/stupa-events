/**
 * The result form of "So lief es" (M5b contract 6): from the stored outcome to the form values and back to the body of
 * `PUT /api/events/{id}/outcome`. Amounts are euros in the form and cents on the wire; "verzichtet" clears the three
 * numbers, a reason is optional. Everything may stay empty.
 */
import type { TranslationKey } from '@core/i18n/translations';
import type { Outcome } from '../api/event.models';
import type { OutcomeIn } from '../model/outcome.models';

export interface OutcomeFormValue {
  attendance: string;
  costs: string;
  revenue: string;
  notes: string;
  waived: boolean;
  waivedReason: string;
}

export const MAX_NOTES = 2000;
export const MAX_WAIVER_REASON = 300;

export type OutcomeErrors = Partial<Record<keyof OutcomeFormValue, TranslationKey>>;
export type OutcomeResult = { ok: true; body: OutcomeIn } | { ok: false; errors: OutcomeErrors };

const euros = (cents: number | null | undefined): string =>
  cents === null || cents === undefined ? '' : (cents / 100).toFixed(2);

export function formFromOutcome(outcome: Outcome | null | undefined): OutcomeFormValue {
  return {
    attendance: outcome?.attendance?.toString() ?? '',
    costs: euros(outcome?.costsCents),
    revenue: euros(outcome?.revenueCents),
    notes: outcome?.notes ?? '',
    waived: outcome?.waived ?? false,
    waivedReason: outcome?.waivedReason ?? '',
  };
}

function wholeNumber(text: string): number | null | 'bad' {
  if (text.trim() === '') return null;
  const n = Number(text);
  return Number.isInteger(n) && n >= 0 ? n : 'bad';
}

function cents(text: string): number | null | 'bad' {
  if (text.trim() === '') return null;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : 'bad';
}

export function toOutcomeIn(v: OutcomeFormValue): OutcomeResult {
  const errors: OutcomeErrors = {};
  const notes = v.notes.trim();
  if (notes.length > MAX_NOTES) errors.notes = 'outcome.errNotes';
  if (v.waived) {
    const reason = v.waivedReason.trim();
    if (Object.keys(errors).length > 0) return { ok: false, errors };
    return {
      ok: true,
      body: {
        attendance: null,
        costsCents: null,
        revenueCents: null,
        notes: notes || null,
        waived: true,
        waivedReason: reason ? reason.slice(0, MAX_WAIVER_REASON) : null,
      },
    };
  }
  const attendance = wholeNumber(v.attendance);
  const costs = cents(v.costs);
  const revenue = cents(v.revenue);
  if (attendance === 'bad') errors.attendance = 'outcome.errAttendance';
  if (costs === 'bad') errors.costs = 'outcome.errAmount';
  if (revenue === 'bad') errors.revenue = 'outcome.errAmount';
  if (attendance === 'bad' || costs === 'bad' || revenue === 'bad' || Object.keys(errors).length > 0)
    return { ok: false, errors };
  return {
    ok: true,
    body: {
      attendance,
      costsCents: costs,
      revenueCents: revenue,
      notes: notes || null,
      waived: false,
      waivedReason: null,
    },
  };
}
