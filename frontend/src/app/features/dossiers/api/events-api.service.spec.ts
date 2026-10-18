import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EventsApi } from './events-api.service';

describe('EventsApi', () => {
  let api: EventsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(EventsApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists with the set query params only', () => {
    api.list({ q: 'movie', state: 'idea', limit: 50, organizationId: '' }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/events');
    expect(req.request.params.get('q')).toBe('movie');
    expect(req.request.params.get('state')).toBe('idea');
    expect(req.request.params.get('limit')).toBe('50');
    expect(req.request.params.has('organizationId')).toBe(false);
    req.flush({ items: [], total: 0, limit: 50, offset: 0 });
  });

  it('posts a transition with and without a note', () => {
    api.transition('e1', 'T02', 'bitte prüfen').subscribe();
    expect(http.expectOne('/api/events/e1/transitions/T02').request.body).toEqual({ note: 'bitte prüfen' });
    api.transition('e1', 'T04').subscribe();
    expect(http.expectOne('/api/events/e1/transitions/T04').request.body).toEqual({});
  });

  it('reads the guards', () => {
    api.guards('e1', 'T04').subscribe();
    expect(http.expectOne('/api/events/e1/guards/T04').request.method).toBe('GET');
  });

  it('uploads a poster as multipart', () => {
    const file = new File(['x'], 'p.png', { type: 'image/png' });
    api.uploadPoster('e1', file, { altText: 'Alt', credit: 'Ich', rightsBasis: 'own_work' }).subscribe();
    const body = http.expectOne('/api/events/e1/poster').request.body as FormData;
    expect(body.get('altText')).toBe('Alt');
    expect(body.get('credit')).toBe('Ich');
    expect(body.get('rightsBasis')).toBe('own_work');
    expect((body.get('file') as File).name).toBe('p.png');
  });

  it('patches, creates, grants the exception and builds the poster URL', () => {
    api.patch('e1', { rev: 1, title: 'x' }).subscribe();
    expect(http.expectOne('/api/events/e1').request.method).toBe('PATCH');
    api.create({} as never).subscribe();
    expect(http.expectOne('/api/events').request.method).toBe('POST');
    api.imageException('e1', 'Offenes Präsidium').subscribe();
    expect(http.expectOne('/api/events/e1/image-exception').request.body).toEqual({ reason: 'Offenes Präsidium' });
    api.get('e1').subscribe();
    http.expectOne('/api/events/e1').flush({});
    expect(api.posterUrl('e1', 'card1200')).toBe('/api/events/e1/poster/file?variant=card1200');
  });

  it('accepts lookups as array or as page', () => {
    let orgs: unknown;
    api.organizations().subscribe((v) => (orgs = v));
    http.expectOne('/api/organizations?creatable=true').flush([{ id: 'o' }]);
    expect(orgs).toEqual([{ id: 'o' }]);
    let cats: unknown;
    api.categories().subscribe((v) => (cats = v));
    http.expectOne('/api/categories').flush({ items: [{ id: 'c' }], total: 1, limit: 1, offset: 0 });
    expect(cats).toEqual([{ id: 'c' }]);
  });
});
