/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/auth/auth.service.spec.ts */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AuthService, loginReturnTo } from './auth.service';
import { IS_INSTALLED_APP } from '../browser/installed-app.token';
import type { Principal } from '../api/models';
import { FSI_MEMBERSHIP } from '../../../testing/event-fixtures';
import {
  createLocationMock,
  provideLocationMock,
  type LocationMock,
} from '../../../testing/location-mock';

const PRINCIPAL: Principal = {
  sub: '1',
  displayName: 'Mia',
  email: 'mia@stupa',
  roles: ['organizer'],
  permissions: ['event.create'],
  groups: ['events-fsi-organizer'],
  organizations: [FSI_MEMBERSHIP],
};

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let location: LocationMock;
  let assign: jest.Mock<void, [string]>;

  beforeEach(() => {
    sessionStorage.clear();
    location = createLocationMock();
    assign = location.assign;
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideLocationMock(location)],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('loads the principal once and exposes permission checks', () => {
    auth.ensureLoaded().subscribe();
    auth.ensureLoaded().subscribe(); // Memoized, so only one HTTP call.
    http.expectOne('/api/auth/me').flush(PRINCIPAL);

    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.can('event.create')).toBe(true);
    expect(auth.can('event.publish')).toBe(false);
    expect(auth.canAny('event.publish', 'event.create')).toBe(true);
    expect(auth.canAny('event.publish')).toBe(false);
    expect(auth.displayName()).toBe('Mia');
    expect(auth.roles()).toEqual(['organizer']);
  });

  it('falls back to email then placeholder for the display name', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush({ ...PRINCIPAL, displayName: null });
    expect(auth.displayName()).toBe('mia@stupa');
  });

  it('stays anonymous when /me returns 401', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(auth.isAuthenticated()).toBe(false);
    expect(auth.can('event.create')).toBe(false);
    expect(auth.displayName()).toBe('-');
  });

  it('redirects to the OIDC login endpoint', () => {
    auth.login();
    expect(assign).toHaveBeenCalledWith('/api/auth/login');
  });

  it('returns to the current page after the login', () => {
    location.pathname = '/dossiers/a1';
    location.search = '?tab=x';
    location.hash = '#comment-c1';
    auth.login();
    expect(assign).toHaveBeenCalledWith(
      '/api/auth/login?returnTo=%2Fdossiers%2Fa1%3Ftab%3Dx%23comment-c1',
    );
  });

  it('marks a started login and clears the mark once a principal loads', () => {
    auth.login();
    expect(sessionStorage.getItem('auth.loginStartedAt')).not.toBeNull();
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
    expect(sessionStorage.getItem('auth.loginStartedAt')).toBeNull();
  });

  it('returns to the target it is given', () => {
    auth.login('/todos/b1?view=list');
    expect(assign).toHaveBeenCalledWith('/api/auth/login?returnTo=%2Ftodos%2Fb1%3Fview%3Dlist');
  });

  it('keeps only safe parts of the return target', () => {
    expect(loginReturnTo('/')).toBeNull();
    expect(loginReturnTo('/api/auth/me')).toBeNull();
    expect(loginReturnTo('https://evil.example/x')).toBeNull();
    expect(loginReturnTo('//evil.example/x')).toBeNull();
    expect(loginReturnTo('/antrag/a1#t=secret')).toBe('/antrag/a1');
    expect(loginReturnTo('/status?t=secret&app=a1')).toBe('/status?app=a1');
    expect(loginReturnTo('/dossiers/a1#comments')).toBe('/dossiers/a1#comments');
    expect(loginReturnTo('/dossiers/a1#comment-0d4c-11')).toBe('/dossiers/a1#comment-0d4c-11');
  });

  it('starts the login of the installed app with client=pwa', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideLocationMock(location),
        { provide: IS_INSTALLED_APP, useValue: () => true },
      ],
    });
    TestBed.inject(AuthService).login();
    expect(assign).toHaveBeenCalledWith('/api/auth/login?client=pwa');
    http = TestBed.inject(HttpTestingController);
  });

  it('logs out, clears the principal and follows the RP logout url', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);

    auth.logout();
    http.expectOne('/api/auth/logout').flush({ logoutUrl: 'https://idp/logout' });

    expect(auth.isAuthenticated()).toBe(false);
    expect(assign).toHaveBeenCalledWith('https://idp/logout');
  });

  it('logs out to home when no RP logout url is returned', () => {
    auth.logout();
    http.expectOne('/api/auth/logout').flush({ logoutUrl: null });
    expect(assign).toHaveBeenCalledWith('/');
  });

  it('logs out gracefully even if the request errors', () => {
    auth.logout();
    http.expectOne('/api/auth/logout').flush(null, { status: 500, statusText: 'Server Error' });
    expect(assign).toHaveBeenCalledWith('/');
  });

  it('falls back to the placeholder display name when name and email are blank', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush({ ...PRINCIPAL, displayName: null, email: '' });
    expect(auth.displayName()).toBe('-');
  });

  it('exposes id, roles and organizations of the principal', () => {
    expect(auth.userId()).toBeNull();
    expect(auth.organizations()).toEqual([]);
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
    expect(auth.userId()).toBe('1');
    expect(auth.organizations()).toEqual([FSI_MEMBERSHIP]);
    expect(auth.isAdmin()).toBe(false);
  });

  it('reads the snake_case wire names of the upstream backend too', () => {
    auth.ensureLoaded().subscribe();
    http
      .expectOne('/api/auth/me')
      .flush({ sub: '2', display_name: 'Max', roles: [], permissions: [], groups: [] });
    expect(auth.displayName()).toBe('Max');
  });

  it('ensureAuthenticated maps the principal presence to a boolean', () => {
    let authed: boolean | undefined;
    auth.ensureAuthenticated().subscribe((v) => (authed = v));
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
    expect(authed).toBe(true);
  });

  it('ensureAuthenticated is false for anonymous (401) sessions', () => {
    let authed: boolean | undefined;
    auth.ensureAuthenticated().subscribe((v) => (authed = v));
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(authed).toBe(false);
  });

  it('grants admins every permission via can()/canAny()', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush({ ...PRINCIPAL, roles: ['admin'], permissions: [] });
    expect(auth.can('anything.at.all')).toBe(true);
    expect(auth.canAny('whatever')).toBe(true);
    // An empty permission list makes canAny true. Any session passes.
    expect(auth.canAny()).toBe(true);
  });

  it('re-loads the principal after logout clears the memoised observable', () => {
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);

    auth.logout();
    http.expectOne('/api/auth/logout').flush({ logoutUrl: null });

    // Logout reset the cached principal$. A new ensureLoaded calls /me again.
    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
    expect(auth.isAuthenticated()).toBe(true);
  });

  it('handleUnauthorized re-authenticates only when a principal was present', () => {
    auth.handleUnauthorized();
    expect(assign).not.toHaveBeenCalled();

    auth.ensureLoaded().subscribe();
    http.expectOne('/api/auth/me').flush(PRINCIPAL);
    auth.handleUnauthorized();

    expect(auth.isAuthenticated()).toBe(false);
    expect(assign).toHaveBeenCalledWith('/api/auth/login');
  });
});
