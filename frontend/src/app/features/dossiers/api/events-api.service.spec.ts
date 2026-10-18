import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EventsApi } from './events-api.service';

describe('EventsApi', () => {
  let api: EventsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(EventsApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists cards with the set query params only and repeats the states', () => {
    api
      .listCards({
        q: 'movie',
        state: ['idea', 'planning'],
        limit: 50,
        organization: '',
        mine: true,
      })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/events');
    expect(req.request.params.get('view')).toBe('list');
    expect(req.request.params.get('q')).toBe('movie');
    expect(req.request.params.getAll('state')).toEqual(['idea', 'planning']);
    expect(req.request.params.get('limit')).toBe('50');
    expect(req.request.params.get('mine')).toBe('1');
    expect(req.request.params.has('organization')).toBe(false);
    req.flush({ items: [], total: 0, limit: 50, offset: 0 });
  });

  it('loads the board view and the tasks', () => {
    api.board({ columnLimit: 50, category: 'kino' }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/events');
    expect(req.request.params.get('view')).toBe('board');
    expect(req.request.params.get('columnLimit')).toBe('50');
    req.flush({ columns: [], generatedAt: 'x' });
    api.tasks().subscribe();
    expect(http.expectOne('/api/tasks').request.method).toBe('GET');
  });

  it('posts a transition with a note, a publish time and the revision as If-Match', () => {
    api.transition('e1', 'T04', { note: 'ok', publishAt: '2026-11-01T10:00:00Z' }, 7).subscribe();
    const req = http.expectOne('/api/events/e1/transitions/T04');
    expect(req.request.body).toEqual({ note: 'ok', publishAt: '2026-11-01T10:00:00Z' });
    expect(req.request.headers.get('If-Match')).toBe('"7"');
    api.transition('e1', 'T05').subscribe();
    const bare = http.expectOne('/api/events/e1/transitions/T05');
    expect(bare.request.body).toEqual({});
    expect(bare.request.headers.has('If-Match')).toBe(false);
  });

  it('posts an action with the revision as If-Match', () => {
    api.action('e1', 'cancel', { reason: 'Krank', publicReasonCode: 'illness' }, 3).subscribe();
    const req = http.expectOne('/api/events/e1/actions/cancel');
    expect(req.request.headers.get('If-Match')).toBe('"3"');
    api.action('e1', 'confirm-flyer').subscribe();
    expect(http.expectOne('/api/events/e1/actions/confirm-flyer').request.body).toEqual({});
  });

  it('reads, writes and drops the draft', () => {
    let draft: unknown = 'unset';
    api.draft('e1').subscribe((d) => (draft = d));
    http.expectOne('/api/events/e1/draft').flush(null, { status: 204, statusText: 'No Content' });
    expect(draft).toBeNull();
    api.draft('e1').subscribe((d) => (draft = d));
    http
      .expectOne('/api/events/e1/draft')
      .flush({ baseRev: 3, fields: { summary: 'x' }, updatedAt: 'y' });
    expect(draft).toEqual({ baseRev: 3, fields: { summary: 'x' }, updatedAt: 'y' });
    api.saveDraft('e1', 3, { summary: 'x' }).subscribe();
    const put = http.expectOne('/api/events/e1/draft');
    expect(put.request.method).toBe('PUT');
    expect(put.request.body).toEqual({ fields: { summary: 'x' } });
    expect(put.request.headers.get('If-Match')).toBe('"3"');
    api.discardDraft('e1').subscribe();
    expect(http.expectOne('/api/events/e1/draft').request.method).toBe('DELETE');
  });

  it('reads the revisions', () => {
    api.revisions('e1', 20, 40).subscribe();
    const req = http.expectOne((r) => r.url === '/api/events/e1/revisions');
    expect(req.request.params.get('limit')).toBe('20');
    expect(req.request.params.get('offset')).toBe('40');
    api.revision('e1', 2).subscribe();
    expect(http.expectOne('/api/events/e1/revisions/2').request.method).toBe('GET');
  });

  it('reads the guards', () => {
    api.guards('e1', 'T04').subscribe();
    expect(http.expectOne('/api/events/e1/guards/T04').request.method).toBe('GET');
  });

  it('uploads a poster as multipart', () => {
    const file = new File(['x'], 'p.png', { type: 'image/png' });
    api
      .uploadPoster('e1', file, {
        altText: 'Alt',
        credit: 'Ich',
        rightsBasis: 'own_work',
        personsDepicted: true,
        consentNote: 'schriftlich',
      })
      .subscribe();
    const body = http.expectOne('/api/events/e1/poster').request.body as FormData;
    expect(body.get('altText')).toBe('Alt');
    expect(body.get('credit')).toBe('Ich');
    expect(body.get('rightsBasis')).toBe('own_work');
    expect(body.get('personsDepicted')).toBe('true');
    expect(body.get('consentNote')).toBe('schriftlich');
    expect((body.get('file') as File).name).toBe('p.png');
  });

  it('patches with the revision as If-Match, creates and builds the poster URL', () => {
    api.patch('e1', 1, { title: 'x', note: 'n' }).subscribe();
    const patch = http.expectOne('/api/events/e1');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.headers.get('If-Match')).toBe('"1"');
    expect(patch.request.body).toEqual({ title: 'x', note: 'n' });
    api.create({} as never).subscribe();
    expect(http.expectOne('/api/events').request.method).toBe('POST');
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
    http
      .expectOne('/api/categories?tree=true')
      .flush({ items: [{ id: 'c' }], total: 1, limit: 1, offset: 0 });
    expect(cats).toEqual([{ id: 'c' }]);
    let venues: unknown;
    api.venues().subscribe((v) => (venues = v));
    http.expectOne('/api/venues').flush([{ id: 'v' }]);
    expect(venues).toEqual([{ id: 'v' }]);
    let all: unknown;
    api.allOrganizations().subscribe((v) => (all = v));
    http.expectOne('/api/organizations').flush([{ id: 'a' }]);
    expect(all).toEqual([{ id: 'a' }]);
  });
});

describe('EventsApi defaults', () => {
  let api: EventsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(EventsApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists and loads the board without a query, with the default page of the revisions', () => {
    api.listCards().subscribe();
    expect(http.expectOne((r) => r.url === '/api/events').request.params.get('view')).toBe('list');
    api.board().subscribe();
    expect(http.expectOne((r) => r.url === '/api/events').request.params.get('view')).toBe('board');
    api.revisions('e1').subscribe();
    const req = http.expectOne((r) => r.url === '/api/events/e1/revisions');
    expect(req.request.params.get('limit')).toBe('50');
    expect(req.request.params.get('offset')).toBe('0');
  });

  it('skips the poster fields that are not set and keeps an empty note out', () => {
    api
      .uploadPoster('e1', new File(['x'], 'p.png'), {
        altText: 'a',
        credit: 'c',
        rightsBasis: 'own_work',
      })
      .subscribe();
    const body = http.expectOne('/api/events/e1/poster').request.body as FormData;
    expect(body.has('personsDepicted')).toBe(false);
    expect(body.has('consentNote')).toBe(false);
  });

  it('reads a draft that comes without a body as none', () => {
    let draft: unknown = 'unset';
    api.draft('e1').subscribe((d) => (draft = d));
    http.expectOne('/api/events/e1/draft').flush(null);
    expect(draft).toBeNull();
  });
});
