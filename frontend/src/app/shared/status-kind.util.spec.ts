/** Spec for the status mapping. */
import { de } from '@core/i18n/translations';
import { type EventState, eventStateStatus } from './status-kind.util';

const STATES: EventState[] = ['draft', 'published', 'archived'];

describe('eventStateStatus', () => {
  it.each(STATES)('maps %s to a label that exists in the catalog', (state) => {
    expect(de[eventStateStatus(state).key]).toBeTruthy();
  });

  it('shows a published event in the accent colour, a draft as ordinary and the archive as muted', () => {
    expect(eventStateStatus('published').kind).toBe('accent');
    expect(eventStateStatus('draft').kind).toBe('neutral');
    expect(eventStateStatus('archived').kind).toBe('muted');
  });
});
