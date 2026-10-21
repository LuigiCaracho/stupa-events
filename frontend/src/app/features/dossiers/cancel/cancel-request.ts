/** Builds and checks the request of the small dialog "Absagen, Verschieben, Wieder ansetzen" (M5b contract 7.1). */
import type { CancelBody, PostponeBody, ReinstateBody } from '../api/action.models';
import { zonedToIso } from '../api/event-time';
import type { PublicReasonCode } from '../api/event.models';

export const REASON_MAX = 500;
export const PUBLIC_TEXT_MAX = 140;

export const PUBLIC_REASON_CODES: readonly PublicReasonCode[] = [
  'none',
  'room',
  'speaker',
  'illness',
  'registration',
  'weather',
  'other',
];

export type CancelMode = 'cancel' | 'postpone' | 'reinstate';

export interface CancelForm {
  mode: CancelMode;
  reason: string;
  code: PublicReasonCode;
  publicText: string;
  newDate: string;
  newTime: string;
  tzid: string;
  now: Date;
}

export type CancelError = 'reasonLong' | 'publicText' | 'newDate' | null;

/** The first error of the form, or `null`. A new date needs both parts and must lie in the future. */
export function cancelError(form: CancelForm): CancelError {
  if (form.reason.trim().length > REASON_MAX) return 'reasonLong';
  if (form.mode === 'reinstate') return null;
  if (form.publicText.trim().length > PUBLIC_TEXT_MAX) return 'publicText';
  if (form.mode === 'postpone' && (form.newDate || form.newTime)) {
    if (!(form.newDate && form.newTime)) return 'newDate';
    if (Date.parse(zonedToIso(form.newDate, form.newTime, form.tzid)) <= form.now.getTime())
      return 'newDate';
  }
  return null;
}

/** The body of `.../cancel`, `.../postpone` or `.../reinstate`; empty texts stay out. */
export function cancelBody(form: CancelForm): CancelBody | PostponeBody | ReinstateBody {
  const reason = form.reason.trim();
  const note = reason ? { reason } : {};
  if (form.mode === 'reinstate') return note;
  const publicText = form.publicText.trim();
  const base: CancelBody = {
    ...note,
    publicReasonCode: form.code,
    ...(publicText && { publicReasonText: publicText }),
  };
  if (form.mode === 'cancel' || !(form.newDate && form.newTime)) return base;
  return { ...base, newStartsAt: zonedToIso(form.newDate, form.newTime, form.tzid) };
}
