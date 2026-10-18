/** Builds and checks the request of the transition dialog (I13): the note rule and `publishAt` of T04. */
import { zonedToIso } from '../api/event-time';
import type { TransitionId, TransitionIn } from '../api/event.models';
import { NOTE_LABEL } from '../api/transitions';

export const NOTE_MAX = 500;
const TZID = 'Europe/Berlin';

export interface TransitionForm {
  transition: TransitionId;
  note: string;
  immediate: boolean;
  publishDate: string;
  publishTime: string;
}

export type FormError = 'noteRequired' | 'noteTooLong' | 'publishAt' | null;

/** The first error of the form, or `null` when the request can go out. */
export function formError(form: TransitionForm): FormError {
  const note = form.note.trim();
  if (NOTE_LABEL[form.transition] && note.length === 0) return 'noteRequired';
  if (note.length > NOTE_MAX) return 'noteTooLong';
  const half = !!form.publishDate !== !!form.publishTime;
  if (form.transition === 'T04' && !form.immediate && half) return 'publishAt';
  return null;
}

/** The body of `POST .../transitions/{T}`; `publishAt` only for T04 with a chosen time. */
export function transitionBody(form: TransitionForm): TransitionIn {
  const note = form.note.trim();
  const scheduled =
    form.transition === 'T04' && !form.immediate && form.publishDate && form.publishTime;
  const publishAt = scheduled ? zonedToIso(form.publishDate, form.publishTime, TZID) : undefined;
  return { ...(note && { note }), ...(publishAt && { publishAt }) };
}
