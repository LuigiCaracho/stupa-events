/** i18n key of the action label of each transition. */
import type { TranslationKey } from '@core/i18n/translations';
import type { TransitionId } from './event.models';

export const TRANSITION_LABEL: Record<TransitionId, TranslationKey> = {
  T01: 'transition.T01',
  T02: 'transition.T02',
  T04: 'transition.T04',
  T05: 'transition.T05',
};
