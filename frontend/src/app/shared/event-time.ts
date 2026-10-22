/** Conversion between wall-clock input in an IANA zone and the UTC instants of the wire. */

interface Zoned {
  date: string;
  time: string;
}

const PARTS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
};

function zoneParts(ms: number, tz: string): Record<string, string> {
  const parts = new Intl.DateTimeFormat('en-US', { ...PARTS, timeZone: tz }).formatToParts(ms);
  return Object.fromEntries(parts.map((p) => [p.type, p.value]));
}

function offsetMs(ms: number, tz: string): number {
  const p = zoneParts(ms, tz);
  const asUtc = Date.UTC(
    +p['year'],
    +p['month'] - 1,
    +p['day'],
    +p['hour'],
    +p['minute'],
    +p['second'],
  );
  return asUtc - Math.floor(ms / 1000) * 1000;
}

/**
 * Turns a wall-clock date and time in `tz` into a UTC ISO instant.
 *
 * Args:
 *   date: `YYYY-MM-DD`.
 *   time: `HH:MM`.
 *   tz: IANA zone name.
 *
 * Returns:
 *   The instant as `YYYY-MM-DDTHH:MM:SSZ`.
 */
export function zonedToIso(date: string, time: string, tz: string): string {
  const [y, mo, d] = date.split('-').map(Number);
  const [h, mi] = time.split(':').map(Number);
  const guess = Date.UTC(y, mo - 1, d, h, mi);
  const settled = guess - offsetMs(guess - offsetMs(guess, tz), tz);
  return new Date(settled).toISOString().replace('.000Z', 'Z');
}

/** Splits a UTC ISO instant into the wall-clock date and time in `tz`. */
export function isoToZoned(iso: string, tz: string): Zoned {
  const p = zoneParts(Date.parse(iso), tz);
  return { date: `${p['year']}-${p['month']}-${p['day']}`, time: `${p['hour']}:${p['minute']}` };
}

/** "Do., 5. Nov., 19:30" in the zone of the event. */
export function formatEventTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: tz,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(Date.parse(iso));
}

/** "Do., 5. Nov." in the zone of the event, for cards and rows. */
export function formatEventDay(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: tz,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(Date.parse(iso));
}

/** "01.11." for the "geplant ab" line of a card. */
export function formatShortDate(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: tz,
    day: '2-digit',
    month: '2-digit',
  }).format(Date.parse(iso));
}

/** "Do., 22. Okt. 2026" in the zone of the event, for the detail page. */
export function formatEventDate(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: tz,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(Date.parse(iso));
}

/** "20:00" in the zone of the event. */
export function formatClock(iso: string, tz: string): string {
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(Date.parse(iso));
}

/** A day key as a local-midnight `Date`, so a date block shows exactly that day in any browser zone. */
export function dayKeyToDate(key: string): Date {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d);
}
