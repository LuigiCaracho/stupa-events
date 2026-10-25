/** Spec for P01 Heute: hero, today and week lists, empty state, error and the category chips. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { runAxe } from '../../../../../testing/a11y';
import { CATEGORIES, card } from '../../../../../testing/public-fixtures';
import { TodayComponent } from './today.component';

let onLine = true;

async function setup(today: object, categories: object = CATEGORIES, todayStatus = 200) {
  const view = await render(TodayComponent, {
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  });
  const http = view.fixture.debugElement.injector.get(HttpTestingController);
  view.fixture.detectChanges();
  http
    .expectOne('/api/public/today')
    .flush(today, todayStatus === 200 ? {} : { status: todayStatus, statusText: 'x' });
  http.expectOne('/api/public/categories').flush(categories);
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return view;
}

const FUTURE = '2099-01-01T18:00:00Z';
const out = (over: object = {}) => ({
  generatedAt: '2026-10-22T08:00:00Z',
  date: '2026-10-22',
  today: [card({ slug: 'a', title: 'Heutiges Event', endsAt: FUTURE })],
  days: [
    {
      date: '2026-10-23',
      items: [card({ slug: 'b', title: 'Morgen-Event', startsOn: '2026-10-23', endsAt: FUTURE })],
    },
  ],
  ...over,
});

describe('TodayComponent freshness and offline', () => {
  beforeEach(() => {
    onLine = true;
    jest.spyOn(window.navigator, 'onLine', 'get').mockImplementation(() => onLine);
  });
  afterEach(() => jest.restoreAllMocks());

  it('says nothing about the age of a fresh answer', async () => {
    await setup(out({ generatedAt: new Date().toISOString() }));
    expect(screen.queryByText(/Stand/)).not.toBeInTheDocument();
  });

  it('names the time of the answer when offline', async () => {
    onLine = false;
    await setup(out({ generatedAt: new Date().toISOString() }));
    expect(screen.getByText(/^Offline, Stand \d\d:\d\d$/)).toBeInTheDocument();
  });

  it('warns about an answer older than an hour on the same day, or from yesterday', async () => {
    await setup(out({ generatedAt: '2020-01-01T08:00:00Z' }));
    expect(screen.getByText(/^Stand von gestern, \d\d:\d\d$/)).toBeInTheDocument();
  });

  it('shows the offline state when the request failed without a network', async () => {
    onLine = false;
    await setup({}, CATEGORIES, 500);
    expect(screen.getByRole('heading', { name: 'Du bist offline.' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zu Heute' })).toBeInTheDocument();
  });
});

describe('TodayComponent', () => {
  it('shows the next event as hero, today and the week with a day heading', async () => {
    await setup(out());
    expect(screen.getByText('Als Nächstes')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Heutiges Event/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Heute am Campus' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Diese Woche' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Fr., 23. Okt.' })).toBeInTheDocument();
  });

  it('skips a cancelled event as hero but keeps it in the list as text', async () => {
    await setup(
      out({
        today: [
          card({ slug: 'x', title: 'Abgesagtes', status: 'cancelled', endsAt: FUTURE }),
          card({ slug: 'y', title: 'Stattfindendes', endsAt: FUTURE }),
        ],
        days: [],
      }),
    );
    expect(document.querySelector('.hero__title')).toHaveTextContent('Stattfindendes');
    expect(screen.getByText('Abgesagt')).toBeInTheDocument();
  });

  it('leads the category chips into the search and leaves out empty categories', async () => {
    await setup(out());
    const chip = screen.getByRole('link', { name: 'Kultur' });
    expect(chip).toHaveAttribute('href', '/suche?category=kultur');
    expect(screen.queryByRole('link', { name: 'Party' })).not.toBeInTheDocument();
  });

  it('says nothing is planned and leads to the calendar when there is nothing at all', async () => {
    await setup(out({ today: [], days: [] }));
    expect(screen.getByText('Heute ist nichts geplant.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zum Kalender' })).toHaveAttribute('href', '/kalender');
  });

  it('shows a reload note when the call fails', async () => {
    await setup({ status: 503 }, CATEGORIES, 503);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Termine konnten nicht geladen werden.',
    );
    expect(screen.getByRole('button', { name: 'Neu laden' })).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await setup(out());
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
