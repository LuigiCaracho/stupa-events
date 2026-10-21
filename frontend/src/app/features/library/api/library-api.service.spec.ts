import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { LibraryApi } from './library-api.service';

describe('LibraryApi', () => {
  let api: LibraryApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(LibraryApi);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('lists with filters, reads a document over the document route and adopts it', () => {
    api.list({ q: 'cafe', kind: 'document', limit: 50 }).subscribe();
    http.expectOne((r) => r.url === '/api/library' && r.params.get('kind') === 'document').flush({});
    api.document('d1').subscribe();
    http.expectOne('/api/documents/d1').flush({});
    api.adopt('d1', 'ev-1').subscribe();
    const req = http.expectOne('/api/library/documents/d1/adopt');
    expect(req.request.body).toEqual({ eventId: 'ev-1' });
    req.flush({});
  });

  it('builds the download and preview URLs of an attachment', () => {
    expect(api.downloadUrl('a1')).toBe('/api/attachments/a1/download');
    expect(api.previewUrl('a1')).toBe('/api/attachments/a1/preview');
  });
});
