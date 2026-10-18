/** i18n key of the action label of each of the 14 transitions (M3 contract 2.2). */
import type { TranslationKey } from '@core/i18n/translations';
import type { TransitionId } from './event.models';

export const TRANSITION_LABEL: Record<TransitionId, TranslationKey> = {
  T01: 'transition.T01',
  T02: 'transition.T02',
  T03: 'transition.T03',
  T04: 'transition.T04',
  T05: 'transition.T05',
  T06: 'transition.T06',
  T07: 'transition.T07',
  T08: 'transition.T08',
  T08b: 'transition.T08b',
  T09: 'transition.T09',
  T09b: 'transition.T09b',
  T10: 'transition.T10',
  T11: 'transition.T11',
  T12: 'transition.T12',
};
