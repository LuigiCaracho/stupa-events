import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FormatsApi } from './formats-api.service';

describe('FormatsApi', () => {
  let api: FormatsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(FormatsApi);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('lists, reads and creates formats', () => {
    api.list({ q: 'movie', limit: 100 }).subscribe();
    http.expectOne((r) => r.url === '/api/formats' && r.params.get('q') === 'movie').flush({});
    api.get('movienight').subscribe();
    http.expectOne('/api/formats/movienight').flush({});
    api.create({ slug: 'x', title: 'X', organizationId: 'o' }).subscribe();
    const post = http.expectOne('/api/formats');
    expect(post.request.method).toBe('POST');
    post.flush({});
  });

  it('patches without If-Match (last writer wins)', () => {
    api.patch('movienight', { title: 'Neu' }).subscribe();
    const req = http.expectOne('/api/formats/movienight');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.headers.has('If-Match')).toBe(false);
    req.flush({});
  });

  it('creates the master howto from a dossier or the scaffold, and verifies', () => {
    api.createHowto('movienight', 'ev-1').subscribe();
    const a = http.expectOne('/api/formats/movienight/howto');
    expect(a.request.body).toEqual({ fromEventId: 'ev-1' });
    a.flush({});
    api.createHowto('movienight').subscribe();
    const b = http.expectOne('/api/formats/movienight/howto');
    expect(b.request.body).toEqual({});
    b.flush({});
    api.verify('movienight').subscribe();
    http.expectOne('/api/formats/movienight/verify').flush({});
  });

  it('plans a new edition, saves a dossier as a format and sets the format of a dossier', () => {
    api.newEdition('movienight', { startsAt: '2026-11-05T18:30:00Z' }).subscribe();
    const a = http.expectOne('/api/formats/movienight/new-edition');
    expect(a.request.body).toEqual({ startsAt: '2026-11-05T18:30:00Z' });
    a.flush({});
    api.saveAsFormat('ev-1', { slug: 'x', title: 'X' }).subscribe();
    http.expectOne('/api/events/ev-1/save-as-format').flush({});
    api.setEventFormat('ev-1', null).subscribe();
    const put = http.expectOne('/api/events/ev-1/format');
    expect(put.request.method).toBe('PUT');
    expect(put.request.body).toEqual({ slug: null });
    put.flush({});
  });
});
