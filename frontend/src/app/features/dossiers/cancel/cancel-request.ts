/** Builds and checks the request of I14 (cancel or postpone): the internal reason, the public reason and the new date. */
import { zonedToIso } from '../api/event-time';
import type { CancelBody, PostponeBody } from '../api/action.models';
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

export type CancelMode = 'cancel' | 'postpone';

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

export type CancelError = 'reason' | 'reasonLong' | 'publicText' | 'newDate' | null;

/** The first error of the form, or `null`. A new date needs both parts and must lie in the future. */
export function cancelError(form: CancelForm): CancelError {
  const reason = form.reason.trim();
  if (!reason) return 'reason';
  if (reason.length > REASON_MAX) return 'reasonLong';
  if (form.publicText.trim().length > PUBLIC_TEXT_MAX) return 'publicText';
  if (form.mode === 'postpone' && (form.newDate || form.newTime)) {
    if (!(form.newDate && form.newTime)) return 'newDate';
    if (Date.parse(zonedToIso(form.newDate, form.newTime, form.tzid)) <= form.now.getTime())
      return 'newDate';
  }
  return null;
}

/** The body of `.../actions/cancel` or `.../actions/postpone`. */
export function cancelBody(
  form: CancelForm,
  mayWritePublicText: boolean,
): CancelBody | PostponeBody {
  const publicText = form.publicText.trim();
  const base: CancelBody = {
    reason: form.reason.trim(),
    publicReasonCode: form.code,
    ...(mayWritePublicText && publicText && { publicReasonText: publicText }),
  };
  if (form.mode === 'cancel' || !(form.newDate && form.newTime)) return base;
  return { ...base, newStartsAt: zonedToIso(form.newDate, form.newTime, form.tzid) };
}
