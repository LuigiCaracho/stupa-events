import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FollowupApi } from './followup-api.service';

describe('FollowupApi', () => {
  let api: FollowupApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(FollowupApi);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('puts the outcome with the revision in If-Match', () => {
    const body = { attendance: 87, costsCents: 0, revenueCents: null, notes: null, waived: false, waivedReason: null };
    api.putOutcome('e1', 4, body).subscribe();
    const req = http.expectOne('/api/events/e1/outcome');
    expect(req.request.method).toBe('PUT');
    expect(req.request.headers.get('If-Match')).toBe('"4"');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('verifies and unverifies the howto on the same route', () => {
    api.verifyHowto('e1').subscribe();
    const post = http.expectOne('/api/events/e1/actions/verify-howto');
    expect(post.request.method).toBe('POST');
    post.flush({});
    api.unverifyHowto('e1').subscribe();
    const del = http.expectOne('/api/events/e1/actions/verify-howto');
    expect(del.request.method).toBe('DELETE');
    del.flush({});
  });

  it('confirms the location with a precision and puts the facts with If-Match', () => {
    api.confirmLocation('e1', 'building').subscribe();
    const loc = http.expectOne('/api/events/e1/actions/confirm-location');
    expect(loc.request.body).toEqual({ precision: 'building' });
    loc.flush({});
    api.putFacts('e1', 2, { ageLimit: 16 }).subscribe();
    const facts = http.expectOne('/api/events/e1/facts');
    expect(facts.request.method).toBe('PUT');
    expect(facts.request.headers.get('If-Match')).toBe('"2"');
    expect(facts.request.body).toEqual({ ageLimit: 16 });
    facts.flush({});
  });
});
