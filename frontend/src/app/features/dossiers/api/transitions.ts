/**
 * Facts about the transitions that the UI needs and the server also enforces: the primary button of
 * each state, which transitions need a note, and which board column a drag may reach (mirror of
 * `BOARD_MOVES` in the backend, M3 contract 5.1). The server stays the authority; `card.moves` wins.
 */
import type { TranslationKey } from '@core/i18n/translations';
import type { EventState } from '@shared/status-kind.util';
import type { ColumnKey } from './board.models';
import type { TransitionId } from './event.models';

export const PRIMARY_TRANSITION: Partial<Record<EventState, TransitionId>> = {
  idea: 'T01',
  planning: 'T02',
  in_review: 'T04',
  approved: 'T05',
  followup: 'T09',
};

export const NOTE_LABEL: Partial<Record<TransitionId, TranslationKey>> = {
  T03: 'transition.noteT03',
  T06: 'transition.noteT06',
  T07: 'transition.noteT07',
  T10: 'transition.noteT10',
  T11: 'transition.noteT11',
};

export const SYSTEM_ONLY: ReadonlySet<TransitionId> = new Set(['T08', 'T08b', 'T09b']);

export const BOARD_MOVES: Readonly<
  Partial<Record<EventState, Partial<Record<ColumnKey, TransitionId>>>>
> = {
  idea: { planning: 'T01' },
  planning: { in_review: 'T02' },
  in_review: { planning: 'T03', published: 'T04' },
  approved: { in_review: 'T06' },
};

/** The transitions of the menu "Mehr": everything but the primary button and the system steps. */
export function menuTransitions(
  state: EventState,
  allowed: readonly TransitionId[],
): TransitionId[] {
  const primary = PRIMARY_TRANSITION[state];
  return allowed.filter((t) => t !== primary && !SYSTEM_ONLY.has(t));
}
