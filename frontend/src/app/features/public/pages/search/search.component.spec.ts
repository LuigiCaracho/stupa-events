/** Spec for P02 Suche: live search with debounce, facets in the URL, "Mehr anzeigen", empty and error states. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { CATEGORIES, card, search } from '../../../../../testing/public-fixtures';
import { SearchComponent } from './search.component';

async function setup(url: string) {
  const { TestBed } = await import('@angular/core/testing');
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: 'suche', component: SearchComponent }], withComponentInputBinding()),
      provideHttpClient(),
      provideHttpClientTesting(),
    ],
  });
  const harness = await RouterTestingHarness.create();
  await harness.navigateByUrl(url, SearchComponent);
  const http = TestBed.inject(HttpTestingController);
  return { harness, http, router: TestBed.inject(Router) };
}

const tick = async (h: { harness: RouterTestingHarness }) => {
  await new Promise((resolve) => setTimeout(resolve, 0));
  h.harness.detectChanges();
};

const events = (http: HttpTestingController) =>
  http.expectOne((r) => r.url === '/api/public/events' && !r.params.has('cursor'));

async function load(h: Awaited<ReturnType<typeof setup>>, body: object, status = 200) {
  h.harness.detectChanges();
  events(h.http).flush(body, status === 200 ? {} : { status, statusText: 'x' });
  h.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
  await h.harness.fixture.whenStable();
  h.harness.detectChanges();
}

describe('SearchComponent', () => {
  it('asks for the filters of the URL and lists the hits with their count', async () => {
    const h = await setup('/suche?q=kino&category=kultur&past=1');
    h.harness.detectChanges();
    const req = events(h.http);
    expect(req.request.params.get('q')).toBe('kino');
    expect(req.request.params.getAll('category')).toEqual(['kultur']);
    expect(req.request.params.get('past')).toBe('1');
    req.flush(search([card(), card({ slug: 'b', title: 'Zweites' })]));
    h.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
    await h.harness.fixture.whenStable();
    h.harness.detectChanges();
    expect(screen.getByRole('link', { name: 'Zweites' })).toBeInTheDocument();
    expect(screen.getAllByText('2 Treffer').length).toBeGreaterThan(0);
  });

  it('searches 250 ms after the last key and writes the text into the URL', async () => {
    jest.useFakeTimers({ advanceTimers: true });
    try {
      const h = await setup('/suche');
      await load(h, search([]));
      const field = screen.getByRole('searchbox', { name: 'Events suchen' });
      await userEvent.type(field, 'kar', { advanceTimers: jest.advanceTimersByTime });
      expect(h.router.url).toBe('/suche');
      jest.advanceTimersByTime(260);
      await tick(h);
      await tick(h);
      expect(h.router.url).toBe('/suche?q=kar');
      events(h.http).flush(search([card({ title: 'Karaoke' })]));
    } finally {
      jest.useRealTimers();
    }
  });

  it('puts a chosen time chip into the URL as a push, so back restores it', async () => {
    const h = await setup('/suche');
    await load(h, search([card()]));
    await userEvent.click(screen.getByRole('button', { name: 'Heute' }));
    await tick(h);
    await tick(h);
    expect(h.router.url).toMatch(/^\/suche\?from=\d{4}-\d{2}-\d{2}&to=\d{4}-\d{2}-\d{2}$/);
    events(h.http).flush(search([]));
  });

  it('appends the next page with "Mehr anzeigen"', async () => {
    const h = await setup('/suche');
    await load(h, search([card()], { nextCursor: 'c1', total: 2 }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr anzeigen' }));
    const more = h.http.expectOne((r) => r.params.get('cursor') === 'c1');
    more.flush(search([card({ slug: 'b', title: 'Zweites' })], { total: null, facets: null }));
    await h.harness.fixture.whenStable();
    h.harness.detectChanges();
    expect(screen.getByRole('link', { name: 'Zweites' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Mehr anzeigen' })).not.toBeInTheDocument();
  });

  it('answers an empty result with the query and the ways out', async () => {
    const h = await setup('/suche?q=xyz&from=2026-10-22&to=2026-10-23');
    await load(h, search([]));
    expect(screen.getByText('Nichts gefunden für „xyz“ in diesem Zeitraum.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Zeitraum erweitern' }));
    await tick(h);
    await tick(h);
    expect(h.router.url).toBe('/suche?q=xyz');
    events(h.http).flush(search([]));
  });

  it.each([
    [422, { status: 422, code: 'query_too_long' }, 'Suchbegriff zu lang.'],
    [429, { status: 429, code: 'rate_limited' }, 'Zu viele Anfragen. Bitte warte einen Moment.'],
    [503, { status: 503 }, 'Die Termine konnten nicht geladen werden.'],
  ])('shows the sentence for %s', async (status, body, text) => {
    const h = await setup('/suche?q=a');
    await load(h, body, status);
    expect(screen.getByRole('alert')).toHaveTextContent(text);
  });

  it('shows cancelled events with their state as text', async () => {
    const h = await setup('/suche');
    await load(h, search([card({ status: 'cancelled' })]));
    expect(screen.getByText('Abgesagt')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const h = await setup('/suche');
    await load(h, search([card()]));
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
