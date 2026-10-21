import {
  addDays,
  clockTime,
  entriesByDay,
  gridRange,
  monthDays,
  periodTitle,
  shiftAnchor,
  startOfWeek,
  todayKey,
  weekDays,
  type GridEntry,
} from './calendar-grid.util';

const entry = (over: Partial<GridEntry>): GridEntry => ({
  id: 'e',
  title: 'Movienight',
  startsAt: '2026-10-29T17:00:00Z',
  startsOn: '2026-10-29',
  endsOn: '2026-10-29',
  allDay: false,
  state: 'published',
  publicStatus: 'scheduled',
  organization: { short: 'FSI', colorToken: 'petrol' },
  ...over,
});

describe('calendar-grid util', () => {
  it('counts days over month and year ends and across the clock change', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addDays('2026-10-25', 1)).toBe('2026-10-26');
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
  });

  it('starts the week on Monday', () => {
    expect(startOfWeek('2026-10-25')).toBe('2026-10-19');
    expect(startOfWeek('2026-10-19')).toBe('2026-10-19');
    expect(weekDays('2026-10-21')[6]).toBe('2026-10-25');
  });

  it('shows six full weeks, with the edge days of the neighbour months', () => {
    const days = monthDays('2026-10-14');
    expect(days).toHaveLength(42);
    expect(days[0]).toBe('2026-09-28');
    expect(days[41]).toBe('2026-11-08');
    expect(gridRange('month', '2026-10-14')).toEqual({ from: '2026-09-28', to: '2026-11-08' });
    expect(gridRange('week', '2026-10-14')).toEqual({ from: '2026-10-12', to: '2026-10-18' });
  });

  it('moves a month to its first day and a week by seven days', () => {
    expect(shiftAnchor('month', '2026-01-31', 1)).toBe('2026-02-01');
    expect(shiftAnchor('month', '2026-01-15', -1)).toBe('2025-12-01');
    expect(shiftAnchor('week', '2026-10-14', 1)).toBe('2026-10-21');
  });

  it('puts a multi-day entry on every day it touches, all-day entries first', () => {
    const trip = entry({ id: 'trip', allDay: true, startsOn: '2026-10-30', endsOn: '2026-11-01' });
    const night = entry({ id: 'night', startsAt: '2026-10-30T18:00:00Z', startsOn: '2026-10-30', endsOn: '2026-10-30' });
    const map = entriesByDay([night, trip], ['2026-10-29', '2026-10-30', '2026-10-31', '2026-11-02']);
    expect(map.get('2026-10-29')).toEqual([]);
    expect(map.get('2026-10-30')?.map((e) => e.id)).toEqual(['trip', 'night']);
    expect(map.get('2026-10-31')?.map((e) => e.id)).toEqual(['trip']);
    expect(map.get('2026-11-02')).toEqual([]);
  });

  it('reads today and the clock in Berlin, not in UTC', () => {
    expect(todayKey(new Date('2026-10-24T22:30:00Z'))).toBe('2026-10-25');
    expect(clockTime('2026-10-24T22:30:00Z')).toBe('00:30');
    expect(clockTime('2026-10-25T01:30:00Z')).toBe('02:30');
    expect(clockTime('2026-10-25T00:30:00Z')).toBe('02:30');
  });

  it('titles a month and a week', () => {
    expect(periodTitle('month', '2026-10-14')).toBe('Oktober 2026');
    expect(periodTitle('week', '2026-10-14')).toContain('–');
  });
});
