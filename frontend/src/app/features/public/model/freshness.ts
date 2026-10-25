/** How old a cached answer is (B4): an hour counts as fresh, another Berlin day as "von gestern". */
import { formatClock, isoToZoned } from '@shared/event-time';

export type Freshness = 'fresh' | 'stale' | 'yesterday';

const HOUR_MS = 3_600_000;
const BERLIN = 'Europe/Berlin';

export function freshnessOf(generatedAt: string, now: number): Freshness {
  const then = Date.parse(generatedAt);
  if (Number.isNaN(then)) return 'fresh';
  const sameDay =
    isoToZoned(generatedAt, BERLIN).date === isoToZoned(new Date(now).toISOString(), BERLIN).date;
  if (!sameDay) return 'yesterday';
  return now - then > HOUR_MS ? 'stale' : 'fresh';
}

/** "14:05" in Berlin time. */
export const standClock = (generatedAt: string): string => formatClock(generatedAt, BERLIN);
