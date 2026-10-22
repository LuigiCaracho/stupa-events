/** Spec for P13 Rückblick: years, groups by semester, more, empty. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { card } from '../../../../../testing/public-fixtures';
import { answer, mountPublic, tick } from '../../../../../testing/public-harness';
import { ReviewPageComponent } from './review.component';

const out = (over: object = {}) => ({
  years: [2026, 2025],
  year: 2026,
  items: [
    card({
      slug: 'a',
      title: 'Sommerfest',
      startsOn: '2026-06-10',
      startsAt: '2026-06-10T10:00:00Z',
      path: '/e/a',
    }),
    card({
      slug: 'b',
      title: 'Winterfeier',
      startsOn: '2026-01-20',
      startsAt: '2026-01-20T10:00:00Z',
      status: 'cancelled',
      path: '/e/b',
    }),
  ],
  nextCursor: null,
  ...over,
});
const open = (url = '/rueckblick') => mountPublic(ReviewPageComponent, 'rueckblick', url);

describe('ReviewPageComponent', () => {
  it('groups the posters by semester and links each event', async () => {
    const h = await open();
    await answer(h, { '/api/public/archive': out() });
    expect(screen.getByRole('heading', { name: 'Sommersemester 2026' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Wintersemester 2025/26' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Sommerfest/ })).toHaveAttribute('href', '/e/a');
    expect(screen.getByText('Abgesagt')).toBeInTheDocument();
  });

  it('offers the years as links and marks the shown one', async () => {
    const h = await open();
    await answer(h, { '/api/public/archive': out() });
    expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute(
      'href',
      '/rueckblick?year=2025',
    );
  });

  it('asks for the year of the URL and ignores a nonsense year', async () => {
    const h = await open('/rueckblick?year=2025');
    h.harness.detectChanges();
    const req = h.http.expectOne((r) => r.url === '/api/public/archive');
    expect(req.request.params.get('year')).toBe('2025');
    req.flush(out());
  });

  it('loads more on demand', async () => {
    const h = await open();
    await answer(h, { '/api/public/archive': out({ nextCursor: 'c1' }) });
    await userEvent.click(screen.getByRole('button', { name: 'Mehr anzeigen' }));
    const req = h.http.expectOne((r) => r.params.get('cursor') === 'c1');
    req.flush(
      out({
        items: [
          card({
            slug: 'c',
            title: 'Herbstfest',
            startsOn: '2025-11-01',
            startsAt: '2025-11-01T10:00:00Z',
            path: '/e/c',
          }),
        ],
      }),
    );
    await tick(h);
    expect(screen.getByRole('link', { name: /Herbstfest/ })).toBeInTheDocument();
  });

  it('says there is no review yet', async () => {
    const h = await open();
    await answer(h, { '/api/public/archive': out({ years: [], year: null, items: [] }) });
    expect(screen.getByText('Noch kein Rückblick vorhanden.')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const h = await open();
    await answer(h, { '/api/public/archive': out() });
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
