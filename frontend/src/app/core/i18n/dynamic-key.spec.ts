import { dynamicKey } from './dynamic-key';

describe('dynamicKey', () => {
  it('finds a key built from snake, camel and kebab case', () => {
    expect(dynamicKey('clone.part', 'venue_text')).toBe('clone.part.venue_text');
    expect(dynamicKey('clone.part', 'venueText')).toBe('clone.part.venue_text');
    expect(dynamicKey('clone.part', 'venue-text')).toBe('clone.part.venue_text');
  });

  it('gives null for an unknown or empty name', () => {
    expect(dynamicKey('clone.part', 'nope')).toBeNull();
    expect(dynamicKey('clone.part', null)).toBeNull();
    expect(dynamicKey('clone.part', '')).toBeNull();
  });
});
