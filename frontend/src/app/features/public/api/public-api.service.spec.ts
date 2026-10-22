/** Spec for the public API client and the error mapping. */
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { publicErrorOf } from './public-error';
import { PublicApi } from './public-api.service';

function setup() {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  return { api: TestBed.inject(PublicApi), http: TestBed.inject(HttpTestingController) };
}

describe('PublicApi', () => {
  it('builds root-relative URLs with repeated filters and no empty values', () => {
    const { api, http } = setup();
    api
      .events({ q: 'kino', category: ['party', 'kultur'], from: '', past: true, limit: 20 })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/public/events');
    expect(req.request.params.getAll('category')).toEqual(['party', 'kultur']);
    expect(req.request.params.get('past')).toBe('1');
    expect(req.request.params.has('from')).toBe(false);
    expect(req.request.params.get('q')).toBe('kino');
    req.flush({ items: [], nextCursor: null, total: 0, facets: null });
  });

  it('encodes the slug of one event', () => {
    const { api, http } = setup();
    api.event('2026-10-22-movienight').subscribe();
    http.expectOne('/api/public/events/2026-10-22-movienight').flush({});
  });

  it('asks for the month with an optional category', () => {
    const { api, http } = setup();
    api.calendar('2026-10', 'party').subscribe();
    const req = http.expectOne((r) => r.url === '/api/public/calendar');
    expect(req.request.params.get('month')).toBe('2026-10');
    expect(req.request.params.get('category')).toBe('party');
    req.flush({ month: '2026-10', truncated: false, days: [] });
  });

  it('asks for today, categories and the archive', () => {
    const { api, http } = setup();
    api.today().subscribe();
    api.categories().subscribe();
    api.archive({ year: 2025, limit: 24 }).subscribe();
    http.expectOne('/api/public/today').flush({});
    http.expectOne('/api/public/categories').flush([]);
    const req = http.expectOne((r) => r.url === '/api/public/archive');
    expect(req.request.params.get('year')).toBe('2025');
    req.flush({ years: [], year: null, items: [], nextCursor: null });
  });
});

describe('publicErrorOf', () => {
  const problem = (status: number, code?: string) =>
    new HttpErrorResponse({ status, error: { status, code } });

  it.each([
    [404, undefined, 'notFound'],
    [429, 'rate_limited', 'rateLimited'],
    [422, 'query_too_long', 'queryTooLong'],
    [422, 'invalid_query', 'invalidQuery'],
    [422, 'invalid_cursor', 'failed'],
    [503, 'search_unavailable', 'failed'],
    [0, undefined, 'failed'],
  ])('maps %s %s to %s', (status, code, kind) => {
    expect(publicErrorOf(problem(status, code))).toBe(kind);
  });
});
