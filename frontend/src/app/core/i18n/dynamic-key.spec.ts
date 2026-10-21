import { dynamicKey } from './dynamic-key';

describe('dynamicKey', () => {
  it('finds a key built from snake, camel and kebab case', () => {
    expect(dynamicKey('event.state', 'in_review')).toBe('event.state.in_review');
    expect(dynamicKey('event.state', 'inReview')).toBe('event.state.in_review');
    expect(dynamicKey('event.state', 'in-review')).toBe('event.state.in_review');
  });

  it('gives null for an unknown or empty name', () => {
    expect(dynamicKey('event.state', 'nope')).toBeNull();
    expect(dynamicKey('event.state', null)).toBeNull();
    expect(dynamicKey('event.state', '')).toBeNull();
  });
});
