/**
 * The model behind the dossier form (pure functions): the form values of an event and a draft, the diff
 * against the event (what `PATCH` and `PUT .../draft` carry), and which fields the person may edit now.
 */
import { isoToZoned, zonedToIso } from '../api/event-time';
import type { EventDto, EventFields } from '../api/event.models';

export interface FormValue {
  title: string;
  summary: string;
  descriptionMd: string;
  costText: string;
  startDate: string;
  startTime: string;
  endDate: string;
  endTime: string;
  venueId: string;
  venueText: string;
  primaryCategoryId: string;
  ticketUrl: string;
  websiteUrl: string;
}

/** The API field(s) behind each form control, for the lock check. */
export const CONTROL_FIELD: Record<keyof FormValue, keyof EventFields> = {
  title: 'title',
  summary: 'summary',
  descriptionMd: 'descriptionMd',
  costText: 'costText',
  startDate: 'startsAt',
  startTime: 'startsAt',
  endDate: 'endsAt',
  endTime: 'endsAt',
  venueId: 'venueId',
  venueText: 'venueText',
  primaryCategoryId: 'primaryCategoryId',
  ticketUrl: 'ticketUrl',
  websiteUrl: 'websiteUrl',
};

const FALLBACK_EDITABLE: readonly (keyof EventFields)[] = Object.values(CONTROL_FIELD);

/** The fields editable now: the server's list, else every field in `idea`/`planning` and none elsewhere. */
export function editableFields(event: EventDto): readonly string[] {
  if (event.editableFields) return event.editableFields;
  return event.state === 'idea' || event.state === 'planning' ? FALLBACK_EDITABLE : [];
}

/** The form values of an event with the fields of a draft laid over them. */
export function valueOf(event: EventDto, draft: EventFields = {}): FormValue {
  const merged = { ...event, ...draft } as EventDto & EventFields;
  const start = isoToZoned(merged.startsAt, event.tzid);
  const end = isoToZoned(merged.endsAt, event.tzid);
  return {
    title: merged.title,
    summary: merged.summary ?? '',
    descriptionMd: merged.descriptionMd ?? '',
    costText: merged.costText ?? '',
    startDate: start.date,
    startTime: start.time,
    endDate: end.date,
    endTime: end.time,
    venueId: ('venueId' in draft ? draft.venueId : event.venueId) ?? '',
    venueText: merged.venueText ?? '',
    primaryCategoryId:
      ('primaryCategoryId' in draft ? draft.primaryCategoryId : event.primaryCategory?.id) ?? '',
    ticketUrl: merged.ticketUrl ?? '',
    websiteUrl: merged.websiteUrl ?? '',
  };
}

type TextField =
  'title' | 'summary' | 'descriptionMd' | 'costText' | 'venueText' | 'ticketUrl' | 'websiteUrl';
const TEXT_FIELDS: readonly TextField[] = [
  'title',
  'summary',
  'descriptionMd',
  'costText',
  'venueText',
  'ticketUrl',
  'websiteUrl',
];

/** The changes of the form against the event, only for fields the person may edit. */
export function diff(event: EventDto, value: FormValue): EventFields {
  const editable = new Set(editableFields(event));
  const out: Record<string, string | null> = {};
  for (const key of TEXT_FIELDS) {
    const now = value[key].trim();
    const before = (event[key] ?? '').trim();
    if (editable.has(key) && now !== before) out[key] = now === '' && key !== 'title' ? null : now;
  }
  const venueBefore = event.venueId ?? '';
  if (editable.has('venueId') && value.venueId !== venueBefore)
    out['venueId'] = value.venueId || null;
  const categoryBefore = event.primaryCategory?.id ?? '';
  if (editable.has('primaryCategoryId') && value.primaryCategoryId !== categoryBefore) {
    out['primaryCategoryId'] = value.primaryCategoryId || null;
  }
  if (editable.has('startsAt') && value.startDate && value.startTime) {
    const iso = zonedToIso(value.startDate, value.startTime, event.tzid);
    if (iso !== event.startsAt) out['startsAt'] = iso;
  }
  if (editable.has('endsAt') && value.endDate && value.endTime) {
    const iso = zonedToIso(value.endDate, value.endTime, event.tzid);
    if (iso !== event.endsAt) out['endsAt'] = iso;
  }
  return out as EventFields;
}

/** True when a link does not start with `https://` (the server refuses it, the form says so first). */
export function badLink(url: string): boolean {
  const value = url.trim();
  return value !== '' && !/^https:\/\/[^/@\s]+\.[^/@\s]+/.test(value);
}

/** True when the end lies before the start (both complete). */
export function endBeforeStart(value: FormValue, tzid: string): boolean {
  if (!(value.startDate && value.startTime && value.endDate && value.endTime)) return false;
  return (
    Date.parse(zonedToIso(value.endDate, value.endTime, tzid)) <
    Date.parse(zonedToIso(value.startDate, value.startTime, tzid))
  );
}
