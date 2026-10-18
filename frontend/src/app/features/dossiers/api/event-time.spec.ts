import { formatEventTime, isoToZoned, zonedToIso } from './event-time';

describe('event-time', () => {
  it('converts summer time (UTC+2) to UTC', () => {
    expect(zonedToIso('2026-07-01', '19:30', 'Europe/Berlin')).toBe('2026-07-01T17:30:00Z');
  });

  it('converts winter time (UTC+1) to UTC', () => {
    expect(zonedToIso('2026-11-05', '19:30', 'Europe/Berlin')).toBe('2026-11-05T18:30:00Z');
  });

  it('handles the day of the switch to winter time', () => {
    expect(zonedToIso('2026-10-25', '12:00', 'Europe/Berlin')).toBe('2026-10-25T11:00:00Z');
  });

  it('splits an instant back into wall-clock parts', () => {
    expect(isoToZoned('2026-11-05T18:30:00Z', 'Europe/Berlin')).toEqual({
      date: '2026-11-05',
      time: '19:30',
    });
    expect(isoToZoned('2026-07-01T22:30:00Z', 'Europe/Berlin')).toEqual({
      date: '2026-07-02',
      time: '00:30',
    });
  });

  it('round-trips', () => {
    const iso = zonedToIso('2027-03-28', '03:15', 'Europe/Berlin');
    expect(isoToZoned(iso, 'Europe/Berlin')).toEqual({ date: '2027-03-28', time: '03:15' });
  });

  it('formats with weekday, day, month and 24 h time', () => {
    const text = formatEventTime('2026-11-05T18:30:00Z', 'Europe/Berlin');
    expect(text).toContain('5');
    expect(text).toContain('19:30');
  });
});
