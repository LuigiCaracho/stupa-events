/** Spec for the status mapping. */
import { de } from '@core/i18n/translations';
import { type EventState, eventStateStatus } from './status-kind.util';

const STATES: EventState[] = [
  'idea',
  'planning',
  'in_review',
  'approved',
  'live',
  'followup',
  'archived',
  'withdrawn',
];

describe('eventStateStatus', () => {
  it.each(STATES)('maps %s to a label that exists in the catalog', (state) => {
    expect(de[eventStateStatus(state).key]).toBeTruthy();
  });

  it('shows a published event in the accent colour and a waiting one as a warning', () => {
    expect(eventStateStatus('live').kind).toBe('accent');
    expect(eventStateStatus('in_review').kind).toBe('warn');
  });
});
