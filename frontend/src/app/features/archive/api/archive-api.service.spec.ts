import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ArchiveApi } from './archive-api.service';

describe('ArchiveApi', () => {
  let api: ArchiveApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(ArchiveApi);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('searches with the filters as parameters and repeats the state', () => {
    api.search({ q: 'kino', scope: 'events', state: ['archived', 'live'], year: '2026', limit: 5 }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/search');
    expect(req.request.params.get('q')).toBe('kino');
    expect(req.request.params.getAll('state')).toEqual(['archived', 'live']);
    expect(req.request.params.get('year')).toBe('2026');
    expect(req.request.params.has('org')).toBe(false);
    req.flush({});
  });

  it('asks for templates, the preview and the clone', () => {
    api.templates({ q: 'movie', format: 'movienight', limit: 50 }).subscribe();
    http.expectOne((r) => r.url === '/api/templates' && r.params.get('format') === 'movienight').flush({});
    api.clonePreview('e1', 'org-1').subscribe();
    http
      .expectOne((r) => r.url === '/api/events/e1/clone-preview' && r.params.get('organizationId') === 'org-1')
      .flush({});
    api.clonePreview('e1').subscribe();
    http.expectOne((r) => r.url === '/api/events/e1/clone-preview' && !r.params.has('organizationId')).flush({});
    api.clone('e1', { startsAt: '2026-11-05T18:00:00Z' }).subscribe();
    const clone = http.expectOne('/api/events/e1/clone');
    expect(clone.request.method).toBe('POST');
    expect(clone.request.body).toEqual({ startsAt: '2026-11-05T18:00:00Z' });
    clone.flush({});
  });

  it('reads last time and the archive dossier', () => {
    api.lastTime('e1').subscribe();
    http.expectOne('/api/events/e1/last-time').flush(null);
    api.event('e1').subscribe();
    http.expectOne('/api/archive/e1').flush({});
  });
});
