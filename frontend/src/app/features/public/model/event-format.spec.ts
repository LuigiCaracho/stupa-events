/** Spec for the display helpers of the public pages. */
import {
  clockOf,
  groupByDay,
  groupBySemester,
  semesterLabel,
  semesterOf,
  endDay,
  startDay,
  statusView,
  whenText,
} from './event-format';

const BASE = {
  startsAt: '2026-10-22T18:00:00Z',
  endsAt: '2026-10-22T20:30:00Z',
  allDay: false,
  startsOn: '2026-10-22',
  endsOn: '2026-10-22',
  tzid: 'Europe/Berlin',
};

describe('whenText', () => {
  it('shows the Berlin day, start and end', () => {
    expect(whenText(BASE)).toBe('Do., 22. Okt. 2026, 20:00 bis 22:30 Uhr');
  });

  it('shows only the start when there is no end', () => {
    expect(whenText({ ...BASE, endsAt: BASE.startsAt })).toBe('Do., 22. Okt. 2026, 20:00 Uhr');
  });

  it('names both days of an event that runs past midnight', () => {
    const text = whenText({ ...BASE, endsAt: '2026-10-23T00:30:00Z', endsOn: '2026-10-23' });
    expect(text).toBe('Do., 22. Okt. 2026, 20:00 Uhr bis Fr., 23. Okt. 2026, 02:30 Uhr');
  });

  it('marks an all-day event and a span of days', () => {
    const allDay = { ...BASE, allDay: true, startsAt: '2026-10-21T22:00:00Z' };
    expect(whenText(allDay)).toBe('Do., 22. Okt. 2026 (ganztägig)');
    const span = { ...allDay, endsAt: '2026-10-23T22:00:00Z', endsOn: '2026-10-24' };
    expect(whenText(span)).toBe('Do., 22. Okt. 2026 bis Sa., 24. Okt. 2026');
  });
});

describe('clockOf and statusView', () => {
  it('gives the clock time of a timed event only', () => {
    expect(clockOf(BASE)).toBe('20:00');
    expect(clockOf({ ...BASE, allDay: true })).toBeNull();
  });

  it('turns cancelled and postponed into text keys, scheduled into nothing', () => {
    expect(statusView('cancelled')?.key).toBe('publicStatus.cancelled');
    expect(statusView('postponed')?.key).toBe('publicStatus.postponed');
    expect(statusView('scheduled')).toBeNull();
  });
});

describe('semesters', () => {
  it.each([
    ['2025-10-01', 'ws2025', 'Wintersemester 2025/26'],
    ['2026-03-31', 'ws2025', 'Wintersemester 2025/26'],
    ['2026-04-01', 'sose2026', 'Sommersemester 2026'],
    ['2026-09-30', 'sose2026', 'Sommersemester 2026'],
    ['2026-12-24', 'ws2026', 'Wintersemester 2026/27'],
  ])('puts %s into %s', (day, key, label) => {
    expect(semesterOf(day).key).toBe(key);
    expect(semesterLabel(semesterOf(day))).toBe(label);
  });

  it('groups a descending list into runs of one semester', () => {
    const groups = groupBySemester([
      { startsAt: BASE.startsAt, startsOn: '2026-05-01' },
      { startsAt: BASE.startsAt, startsOn: '2026-03-01' },
      { startsAt: BASE.startsAt, startsOn: '2025-11-01' },
      { startsAt: BASE.startsAt, startsOn: '2025-05-01' },
    ]);
    expect(groups.map((g) => [g.label, g.items.length])).toEqual([
      ['Sommersemester 2026', 1],
      ['Wintersemester 2025/26', 2],
      ['Sommersemester 2025', 1],
    ]);
  });
});

describe('groupByDay', () => {
  it('starts a group per start day', () => {
    const groups = groupByDay([
      { startsAt: BASE.startsAt, startsOn: 'a' },
      { startsAt: BASE.startsAt, startsOn: 'a' },
      { startsAt: BASE.startsAt, startsOn: 'b' },
    ]);
    expect(groups.map((g) => g.items.length)).toEqual([2, 1]);
  });
});

describe('startDay and endDay', () => {
  const timed = { ...BASE, startsOn: null, endsOn: null };

  it('derive the Berlin days of a timed event, which carries no startsOn', () => {
    expect(startDay({ ...timed, startsAt: '2026-10-22T22:30:00Z' })).toBe('2026-10-23');
    expect(endDay({ ...timed, endsAt: '2026-10-22T22:30:00Z' })).toBe('2026-10-23');
  });

  it('prefer the given days of an all-day event', () => {
    expect(startDay(BASE)).toBe('2026-10-22');
  });

  it('keep whenText and the grouping working without startsOn', () => {
    expect(whenText(timed)).toBe('Do., 22. Okt. 2026, 20:00 bis 22:30 Uhr');
    expect(groupByDay([timed, timed]).map((g) => g.date)).toEqual(['2026-10-22']);
    expect(groupBySemester([timed])[0].label).toBe('Wintersemester 2026/27');
  });
});
