import { freshnessOf, standClock } from './freshness';

const NOW = Date.parse('2026-10-25T12:00:00Z');

describe('freshnessOf', () => {
  it('is fresh within the hour', () => {
    expect(freshnessOf('2026-10-25T11:30:00Z', NOW)).toBe('fresh');
  });

  it('is stale after more than an hour on the same Berlin day', () => {
    expect(freshnessOf('2026-10-25T08:00:00Z', NOW)).toBe('stale');
  });

  it('is "yesterday" on another Berlin day, even within a few hours', () => {
    expect(freshnessOf('2026-10-24T21:30:00Z', Date.parse('2026-10-24T22:30:00Z'))).toBe(
      'yesterday',
    );
    expect(freshnessOf('2026-10-24T11:00:00Z', NOW)).toBe('yesterday');
  });

  it('treats an unreadable stamp as fresh', () => {
    expect(freshnessOf('x', NOW)).toBe('fresh');
  });

  it('prints the clock in Berlin time', () => {
    expect(standClock('2026-10-25T12:05:00Z')).toBe('13:05');
  });
});
