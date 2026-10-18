/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/status-kind.util.ts (rewritten) */
/**
 * The colour of a status, in one place. Rewritten from the workflow tool: the workflow statuses (meetings, votes,
 * invoices) are gone, the event states of the pipeline replace them.
 *
 * The design system shows a status as text in a colour: no dot, no pill. There are five
 * colours and no more, so that the one accent colour keeps its meaning:
 *
 * - `accent`: done and good, or running now (Veröffentlicht).
 * - `warn`: it waits for somebody (Freigabe).
 * - `error`: it failed or was refused.
 * - `neutral`: an ordinary state (Planung, Freigegeben).
 * - `muted`: it is no longer relevant or not yet started (Idee, Archiv, Zurückgezogen).
 *
 * `app-status-text` draws the result.
 */
import type { TranslationKey } from '@core/i18n/translations';

/** The five status colours of the design system. */
export type StatusKind = 'accent' | 'warn' | 'error' | 'neutral' | 'muted';

/** A status as the UI shows it: the colour and the translation key of the label. */
export interface StatusView {
  kind: StatusKind;
  key: TranslationKey;
}

/** The eight states of an event dossier (`event_state`, PLAN 4.1). */
export type EventState =
  | 'idea'
  | 'planning'
  | 'in_review'
  | 'approved'
  | 'live'
  | 'followup'
  | 'archived'
  | 'withdrawn';

const EVENT_STATE: Record<EventState, StatusView> = {
  idea: { kind: 'muted', key: 'event.state.idea' },
  planning: { kind: 'neutral', key: 'event.state.planning' },
  in_review: { kind: 'warn', key: 'event.state.in_review' },
  approved: { kind: 'neutral', key: 'event.state.approved' },
  live: { kind: 'accent', key: 'event.state.live' },
  followup: { kind: 'neutral', key: 'event.state.followup' },
  archived: { kind: 'muted', key: 'event.state.archived' },
  withdrawn: { kind: 'muted', key: 'event.state.withdrawn' },
};

/** The colour and label key of an event state. */
export function eventStateStatus(state: EventState): StatusView {
  return EVENT_STATE[state];
}
