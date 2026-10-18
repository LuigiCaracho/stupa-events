/** Spec for the shell API client and the Problem+JSON reader. */
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiClient, toPrincipal } from './api-client.service';
import { problemOf } from './problem';

describe('ApiClient', () => {
  let api: ApiClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(ApiClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('reads /auth/me in the camelCase contract shape', () => {
    let me: unknown;
    api.me().subscribe((p) => (me = p));
    http.expectOne('/api/auth/me').flush({
      sub: 's',
      email: 'a@b',
      displayName: 'A',
      roles: ['editor'],
      permissions: ['event.publish'],
      groups: ['events-editor'],
      organizations: [{ slug: 'fsi', role: 'organizer' }],
    });
    expect(me).toEqual({
      sub: 's',
      email: 'a@b',
      displayName: 'A',
      roles: ['editor'],
      permissions: ['event.publish'],
      groups: ['events-editor'],
      organizations: [{ slug: 'fsi', role: 'organizer' }],
    });
  });

  it('fills defaults for missing optional fields', () => {
    expect(toPrincipal({ sub: 'x' })).toEqual({
      sub: 'x',
      email: null,
      displayName: null,
      roles: [],
      permissions: [],
      groups: [],
      organizations: [],
    });
  });

  it.each([
    [{ logoutUrl: 'https://idp/out' }, 'https://idp/out'],
    [{ logout_url: 'https://idp/out' }, 'https://idp/out'],
    [{}, null],
  ])('maps the logout answer %j', (wire, expected) => {
    let url: string | null | undefined;
    api.logout().subscribe((r) => (url = r.logoutUrl));
    http.expectOne({ method: 'POST', url: '/api/auth/logout' }).flush(wire);
    expect(url).toBe(expected);
  });
});

describe('problemOf', () => {
  it('returns the Problem+JSON body of an HTTP error, including the reasons', () => {
    const body = {
      status: 422,
      code: 'image_required',
      reasons: [
        { code: 'image_required', field: null, severity: 'blocker', messageKey: 'guards.image_required', fixAction: 'upload_poster' },
      ],
    };
    const err = new HttpErrorResponse({ status: 422, error: body });
    expect(problemOf(err)).toEqual(body);
  });

  it('falls back to the bare status when the body is not a problem object', () => {
    expect(problemOf(new HttpErrorResponse({ status: 502, error: 'Bad Gateway' }))).toEqual({ status: 502 });
  });

  it('returns status 0 for anything that is not an HTTP error', () => {
    expect(problemOf(new Error('x'))).toEqual({ status: 0 });
  });
});
