import { makeCalendarEntry } from '../../../../testing/m5-fixtures';
import { toGridEntry } from './calendar-entries';

describe('toGridEntry', () => {
  it('keeps the local dates of the server', () => {
    const g = toGridEntry(makeCalendarEntry({ startsOn: '2026-10-20', endsOn: '2026-10-21', allDay: true }));
    expect([g.startsOn, g.endsOn]).toEqual(['2026-10-20', '2026-10-21']);
  });

  it('derives the days from the instants in Berlin when the server sends none', () => {
    const g = toGridEntry(
      makeCalendarEntry({ startsOn: null, endsOn: null, startsAt: '2026-10-20T22:30:00Z', endsAt: '2026-10-21T00:30:00Z' }),
    );
    expect([g.startsOn, g.endsOn]).toEqual(['2026-10-21', '2026-10-21']);
  });

  it('ends an entry that stops at midnight on the day before', () => {
    const g = toGridEntry(
      makeCalendarEntry({ startsOn: null, endsOn: null, startsAt: '2026-10-20T19:00:00Z', endsAt: '2026-10-20T22:00:00Z' }),
    );
    expect([g.startsOn, g.endsOn]).toEqual(['2026-10-20', '2026-10-20']);
  });

  it('never ends before it starts (an entry of no length)', () => {
    const g = toGridEntry(
      makeCalendarEntry({ startsOn: null, endsOn: null, startsAt: '2026-10-20T22:00:00Z', endsAt: '2026-10-20T22:00:00Z' }),
    );
    expect(g.endsOn >= g.startsOn).toBe(true);
  });

  it('works for an entry without an organization', () => {
    expect(toGridEntry(makeCalendarEntry({ organization: null })).organization).toBeNull();
  });
});
