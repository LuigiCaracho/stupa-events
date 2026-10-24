/** Spec for the subscription client: the token travels in a header, never in the URL, and no call asks for credentials. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import type { Observable } from 'rxjs';
import { SubscriptionsApi } from './subscriptions-api.service';

describe('SubscriptionsApi', () => {
  let api: SubscriptionsApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(SubscriptionsApi);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('reads the questionnaire without credentials', () => {
    api.questions().subscribe();
    const req = http.expectOne('/api/public/getstarted/questions');
    expect(req.request.withCredentials).toBe(false);
    req.flush({});
  });

  it('sends the manage token as a header and keeps it out of the URL', () => {
    api.me('tok-123').subscribe();
    const req = http.expectOne('/api/public/subscriptions/me');
    expect(req.request.headers.get('X-Subscription-Token')).toBe('tok-123');
    expect(req.request.url).not.toContain('tok-123');
    expect(req.request.withCredentials).toBe(false);
    req.flush({});
  });

  it.each([
    ['updateMe', () => api.updateMe('t', { mailEnabled: false }), 'PUT', '/me'],
    ['rotateIcsToken', () => api.rotateIcsToken('t'), 'POST', '/me/ics-token'],
    ['deleteMe', () => api.deleteMe('t'), 'DELETE', '/me'],
  ])('%s uses the header on %s %s', (_name, call, method, path) => {
    (call() as Observable<unknown>).subscribe();
    const req = http.expectOne(`/api/public/subscriptions${path}`);
    expect(req.request.method).toBe(method);
    expect(req.request.headers.get('X-Subscription-Token')).toBe('t');
    req.flush(null);
  });

  it('posts the DOI token in the body of preview and confirm', () => {
    api.confirmPreview('abc').subscribe();
    api.confirm('abc').subscribe();
    const preview = http.expectOne('/api/public/subscriptions/confirm/preview');
    const confirm = http.expectOne('/api/public/subscriptions/confirm');
    expect(preview.request.body).toEqual({ token: 'abc' });
    expect(confirm.request.body).toEqual({ token: 'abc' });
    expect(confirm.request.headers.has('X-Subscription-Token')).toBe(false);
    preview.flush({ categories: [] });
    confirm.flush({ status: 'confirmed' });
  });

  it('posts the manage-link request with the ALTCHA solution', () => {
    api.requestManageLink('a@b.de', 'sol').subscribe();
    const req = http.expectOne('/api/public/subscriptions/manage-link');
    expect(req.request.body).toEqual({ email: 'a@b.de', altcha: 'sol' });
    req.flush({});
  });
});
