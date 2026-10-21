/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/shared/status-kind.util.ts (rewritten) */
/**
 * The colour of a status, in one place. Rewritten from the workflow tool: the workflow statuses (meetings, votes,
 * invoices) are gone, the three event states replace them.
 *
 * The design system shows a status as text in a colour: no dot, no pill. There are five
 * colours and no more, so that the one accent colour keeps its meaning:
 *
 * - `accent`: done and good, or running now (Veröffentlicht).
 * - `warn`: it needs attention (Verschoben, ungeprüfte Anleitung).
 * - `error`: it failed or was refused.
 * - `neutral`: an ordinary state (Entwurf).
 * - `muted`: it is no longer relevant (Archiv).
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

/** The three states of an event dossier (`event.state`, M5b contract 2.1). */
export type EventState = 'draft' | 'published' | 'archived';

const EVENT_STATE: Record<EventState, StatusView> = {
  draft: { kind: 'neutral', key: 'event.state.draft' },
  published: { kind: 'accent', key: 'event.state.published' },
  archived: { kind: 'muted', key: 'event.state.archived' },
};

/** The colour and label key of an event state. */
export function eventStateStatus(state: EventState): StatusView {
  return EVENT_STATE[state];
}
