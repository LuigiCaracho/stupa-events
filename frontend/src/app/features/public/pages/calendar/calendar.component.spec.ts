/** Spec for P03 Kalender: month from the URL, grid and agenda, month steps, category filter, empty and error. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { CATEGORIES } from '../../../../../testing/public-fixtures';
import { answer, mountPublic, tick } from '../../../../../testing/public-harness';
import { CalendarPageComponent } from './calendar.component';

const ENTRY = {
  slug: 'movienight',
  title: 'Movienight',
  startsAt: '2026-10-22T18:00:00Z',
  endsAt: '2026-10-22T20:00:00Z',
  allDay: false,
  startsOn: '2026-10-22',
  endsOn: '2026-10-22',
  status: 'scheduled',
  categorySlug: 'kultur',
};
const month = (days: object[] = [{ date: '2026-10-22', count: 1, items: [ENTRY] }]) => ({
  month: '2026-10',
  truncated: false,
  days,
});

const open = (url = '/kalender?month=2026-10') =>
  mountPublic(CalendarPageComponent, 'kalender', url);

describe('CalendarPageComponent', () => {
  it('asks for the month of the URL and shows the event in the grid', async () => {
    const h = await open();
    h.harness.detectChanges();
    const req = h.http.expectOne((r) => r.url === '/api/public/calendar');
    expect(req.request.params.get('month')).toBe('2026-10');
    expect(req.request.params.has('category')).toBe(false);
    req.flush(month());
    h.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
    await tick(h);
    await tick(h);
    expect(screen.getByRole('heading', { name: 'Oktober 2026' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Movienight/ })).toBeInTheDocument();
  });

  it('passes the category of the URL on and links the matching subscription', async () => {
    const h = await open('/kalender?month=2026-10&category=party');
    h.harness.detectChanges();
    const req = h.http.expectOne((r) => r.url === '/api/public/calendar');
    expect(req.request.params.get('category')).toBe('party');
    req.flush(month());
    h.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
    await tick(h);
    expect(screen.getByRole('link', { name: 'Diesen Kalender abonnieren' })).toHaveAttribute(
      'href',
      '/abos#k=party',
    );
  });

  it('steps to the next month in the URL', async () => {
    const h = await open();
    await answer(h, { '/api/public/calendar': month(), '/api/public/categories': CATEGORIES });
    await userEvent.click(screen.getByRole('button', { name: 'Weiter' }));
    await tick(h);
    expect(h.router.url).toBe('/kalender?month=2026-11');
    h.http.match((r) => r.url === '/api/public/calendar').forEach((r) => r.flush(month([])));
  });

  it('says that the month is empty', async () => {
    const h = await open();
    await answer(h, { '/api/public/calendar': month([]), '/api/public/categories': CATEGORIES });
    expect(screen.getByText('In diesem Monat ist nichts eingetragen.')).toBeInTheDocument();
  });

  it('falls back to this month for a month outside the range', async () => {
    const h = await open('/kalender?month=1999-01');
    h.harness.detectChanges();
    const req = h.http.expectOne((r) => r.url === '/api/public/calendar');
    expect(req.request.params.get('month')).not.toBe('1999-01');
    req.flush(month([]));
    h.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
  });

  it('shows the reload note on failure', async () => {
    const h = await open();
    await answer(h, {
      '/api/public/calendar': { status: 503, body: { status: 503 } },
      '/api/public/categories': CATEGORIES,
    });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Termine konnten nicht geladen werden.',
    );
  });

  it('has no axe violations', async () => {
    const h = await open();
    await answer(h, { '/api/public/calendar': month(), '/api/public/categories': CATEGORIES });
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
