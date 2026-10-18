/** Copied from STUPA-Workflow@93c33d6 frontend/src/app/core/auth/auth.guard.spec.ts */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import {
  type ActivatedRouteSnapshot,
  type RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';
import { isObservable, type Observable } from 'rxjs';
import { authGuard } from './auth.guard';
import { ToastService } from '@stupa-makers/ui-kit';
import type { Principal } from '../api/models';
import { FSI_MEMBERSHIP } from '../../../testing/event-fixtures';
import {
  createLocationMock,
  provideLocationMock,
  type LocationMock,
} from '../../../testing/location-mock';

const MEMBER: Principal = {
  sub: '1',
  displayName: 'Mia',
  email: 'mia@stupa',
  roles: ['organizer'],
  permissions: ['event.read'],
  groups: ['events-fsi-organizer'],
  organizations: [FSI_MEMBERSHIP],
};

describe('authGuard', () => {
  let http: HttpTestingController;
  let location: LocationMock;
  let assign: jest.Mock<void, [string]>;

  beforeEach(() => {
    sessionStorage.clear();
    location = createLocationMock();
    assign = location.assign;
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        provideLocationMock(location),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  /** Runs the guard, flushes the `/me` probe and returns the result. */
  function run(
    data: Record<string, unknown>,
    principal: Principal | null,
  ): boolean | UrlTree {
    let result!: boolean | UrlTree;
    TestBed.runInInjectionContext(() => {
      const out = authGuard(
        { data } as unknown as ActivatedRouteSnapshot,
        {} as RouterStateSnapshot,
      );
      (out as Observable<boolean | UrlTree>).subscribe((r) => (result = r));
    });
    http.expectOne('/api/auth/me').flush(principal, principal ? {} : { status: 401, statusText: 'Unauthorized' });
    return result;
  }

  it('returns an Observable', () => {
    TestBed.runInInjectionContext(() => {
      const out = authGuard(
        { data: {} } as unknown as ActivatedRouteSnapshot,
        {} as RouterStateSnapshot,
      );
      expect(isObservable(out)).toBe(true);
      (out as Observable<unknown>).subscribe();
    });
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
  });

  it('redirects anonymous users to OIDC login and blocks the route', () => {
    expect(run({}, null)).toBe(false);
    expect(assign).toHaveBeenCalledWith('/api/auth/login');
  });

  it('returns to the blocked target after the login', () => {
    let result!: boolean | UrlTree;
    TestBed.runInInjectionContext(() => {
      const out = authGuard(
        { data: {} } as unknown as ActivatedRouteSnapshot,
        { url: '/dossiers/a1#abschnitt' } as RouterStateSnapshot,
      );
      (out as Observable<boolean | UrlTree>).subscribe((r) => (result = r));
    });
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(result).toBe(false);
    expect(assign).toHaveBeenCalledWith('/api/auth/login?returnTo=%2Fdossiers%2Fa1%23abschnitt');
  });

  it('goes to the login page instead of looping when a login just came back without a session', () => {
    sessionStorage.setItem('auth.loginStartedAt', String(Date.now() - 5_000));
    const result = run({}, null);
    expect(result).toBeInstanceOf(UrlTree);
    expect(String(result)).toBe('/login');
    expect(assign).not.toHaveBeenCalled();
    expect(sessionStorage.getItem('auth.loginStartedAt')).toBeNull();
  });

  it('logs in again when the last login is older than a minute', () => {
    sessionStorage.setItem('auth.loginStartedAt', String(Date.now() - 120_000));
    expect(run({}, null)).toBe(false);
    expect(assign).toHaveBeenCalledWith('/api/auth/login');
    expect(sessionStorage.getItem('auth.loginStartedAt')).not.toBeNull();
  });

  it('allows an authenticated user when no permission is required', () => {
    expect(run({}, MEMBER)).toBe(true);
  });

  it('allows when the principal holds a required permission', () => {
    expect(run({ permission: 'event.read' }, MEMBER)).toBe(true);
  });

  it('allows when the principal holds any of several required permissions', () => {
    expect(run({ permission: ['event.publish', 'event.read'] }, MEMBER)).toBe(true);
  });

  it('redirects to the forbidden page and toasts when the permission is missing', () => {
    const toast = TestBed.inject(ToastService);
    const toastSpy = jest.spyOn(toast, 'error');
    const result = run({ permission: 'event.publish' }, MEMBER);
    expect(result).toBeInstanceOf(UrlTree);
    expect((result as UrlTree).toString()).toBe('/forbidden');
    expect(toastSpy).toHaveBeenCalled();
  });
});
