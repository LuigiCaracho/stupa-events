/** Spec for the calendar adapter. */
import { anchorOf, gridEntries, monthOf, toGridEntry } from './calendar-entries';
import type { PublicCalendarEntry, PublicCalendarOut } from './public.models';

const ENTRY: PublicCalendarEntry = {
  slug: 'movienight',
  title: 'Movienight',
  startsAt: '2026-10-22T18:00:00Z',
  endsAt: '2026-10-22T20:00:00Z',
  allDay: false,
  startsOn: '2026-10-22',
  endsOn: '2026-10-23',
  status: 'cancelled',
  categorySlug: 'kultur',
};

describe('calendar adapter', () => {
  it('maps an entry to a published grid entry that keeps the public status', () => {
    expect(toGridEntry(ENTRY)).toMatchObject({
      id: 'movienight',
      state: 'published',
      publicStatus: 'cancelled',
      organization: null,
    });
  });

  it('lists a multi-day event once', () => {
    const out: PublicCalendarOut = {
      month: '2026-10',
      truncated: false,
      days: [
        { date: '2026-10-22', count: 1, items: [ENTRY] },
        { date: '2026-10-23', count: 1, items: [ENTRY] },
      ],
    };
    expect(gridEntries(out)).toHaveLength(1);
    expect(gridEntries(null)).toEqual([]);
  });

  it('converts between month key and anchor day', () => {
    expect(monthOf('2026-10-22')).toBe('2026-10');
    expect(anchorOf('2026-10')).toBe('2026-10-01');
  });
});
