/**
 * The "Rahmen" of a dossier by the profile of its main category (M5 contract 3.6, PLAN 3.4): which fields a profile has,
 * how the form text becomes the JSON of `PUT /api/events/{id}/facts`, and back. Keys are camelCase on the wire. Empty
 * fields are left out, so the server's `extra=forbid` model sees only what was filled in. Amounts are euros in the form
 * and `budgetCents` on the wire.
 */
import type { TranslationKey } from '@core/i18n/translations';
import { isoToZoned, zonedToIso } from '@shared/event-time';
import type { RequiredProfile } from '../api/event.models';

const TZID = 'Europe/Berlin';
/** A sign-up deadline is a day; the server wants an instant, so it ends at the end of that day. */
const DEADLINE_TIME = '23:59';

export type FactKind = 'int' | 'text' | 'textarea' | 'bool' | 'cents' | 'age' | 'deadline' | 'url';

export interface FactField {
  key: string;
  kind: FactKind;
  label: TranslationKey;
  required?: boolean;
}

export const PROFILES: Record<RequiredProfile, readonly FactField[]> = {
  generic: [
    { key: 'capacity', kind: 'int', label: 'facts.capacity' },
    { key: 'budgetCents', kind: 'cents', label: 'facts.budget' },
  ],
  party: [
    { key: 'ageLimit', kind: 'age', label: 'facts.ageLimit', required: true },
    { key: 'capacity', kind: 'int', label: 'facts.capacity' },
    { key: 'securityPlanDone', kind: 'bool', label: 'facts.securityPlanDone' },
    { key: 'noisePermitRef', kind: 'text', label: 'facts.noisePermitRef' },
    { key: 'budgetCents', kind: 'cents', label: 'facts.budget' },
  ],
  meeting: [
    { key: 'agendaMd', kind: 'textarea', label: 'facts.agenda' },
    { key: 'quorumNeeded', kind: 'int', label: 'facts.quorumNeeded' },
    { key: 'protocolOwner', kind: 'text', label: 'facts.protocolOwner' },
  ],
  trip: [
    { key: 'meetingPoint', kind: 'text', label: 'facts.meetingPoint' },
    { key: 'priceText', kind: 'text', label: 'facts.priceText' },
    { key: 'minParticipants', kind: 'int', label: 'facts.minParticipants' },
    { key: 'maxParticipants', kind: 'int', label: 'facts.maxParticipants' },
    { key: 'signupUrl', kind: 'url', label: 'facts.signupUrl' },
    { key: 'signupDeadline', kind: 'deadline', label: 'facts.signupDeadline' },
  ],
};

export type FactsFormValue = Record<string, string | boolean>;

export function fieldsOf(profile: RequiredProfile | undefined): readonly FactField[] {
  return PROFILES[profile ?? 'generic'];
}

export function formFromFacts(
  profile: RequiredProfile | undefined,
  facts: Record<string, unknown> | null | undefined,
): FactsFormValue {
  return Object.fromEntries(
    fieldsOf(profile).map((f): [string, string | boolean] => {
      const raw = facts?.[f.key];
      if (f.kind === 'bool') return [f.key, raw === true];
      if (raw === undefined || raw === null) return [f.key, ''];
      if (f.kind === 'cents') return [f.key, (Number(raw) / 100).toFixed(2)];
      if (f.kind === 'deadline') return [f.key, isoToZoned(String(raw), TZID).date];
      return [f.key, String(raw)];
    }),
  );
}

export type FactsResult =
  { ok: true; facts: Record<string, unknown> } | { ok: false; errors: Record<string, TranslationKey> };

export function toFacts(profile: RequiredProfile | undefined, form: FactsFormValue): FactsResult {
  const facts: Record<string, unknown> = {};
  const errors: Record<string, TranslationKey> = {};
  for (const f of fieldsOf(profile)) {
    const raw = form[f.key];
    if (f.kind === 'bool') {
      if (raw === true) facts[f.key] = true;
      continue;
    }
    const text = typeof raw === 'string' ? raw.trim() : '';
    if (text === '') continue;
    if (f.kind === 'int' || f.kind === 'age') {
      const n = Number(text);
      if (!Number.isInteger(n) || n < 0) errors[f.key] = 'facts.errNumber';
      else facts[f.key] = n;
    } else if (f.kind === 'cents') {
      const n = Number(text);
      if (!Number.isFinite(n) || n < 0) errors[f.key] = 'facts.errNumber';
      else facts[f.key] = Math.round(n * 100);
    } else if (f.kind === 'url' && !/^https:\/\//.test(text)) {
      errors[f.key] = 'facts.errUrl';
    } else if (f.kind === 'deadline') {
      facts[f.key] = zonedToIso(text, DEADLINE_TIME, TZID);
    } else facts[f.key] = text;
  }
  const min = facts['minParticipants'];
  const max = facts['maxParticipants'];
  if (typeof min === 'number' && typeof max === 'number' && min > max)
    errors['maxParticipants'] = 'facts.errRange';
  return Object.keys(errors).length > 0 ? { ok: false, errors } : { ok: true, facts };
}
