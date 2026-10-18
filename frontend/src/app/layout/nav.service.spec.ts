/** Spec for the navigation model. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '@core/auth/auth.service';
import { createLocationMock, provideLocationMock } from '../../testing/location-mock';
import { routes } from '../app.routes';
import { BOTTOM_BAR_KEYS, NAV_ITEMS, NavService } from './nav.service';

function keysFor(signedIn: boolean, me: { roles?: string[]; permissions?: string[] } = {}): string[] {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), provideLocationMock(createLocationMock())],
  });
  TestBed.inject(AuthService).ensureLoaded().subscribe();
  const req = TestBed.inject(HttpTestingController).expectOne('/api/auth/me');
  if (signedIn) req.flush({ sub: '1', roles: [], permissions: [], groups: [], organizations: [], ...me });
  else req.flush(null, { status: 401, statusText: 'Unauthorized' });
  return TestBed.inject(NavService).visible().map((i) => i.key);
}

describe('NavService', () => {
  it('shows Aufgaben, Dossiers and Konto to a signed-in principal', () => {
    expect(keysFor(true)).toEqual(['tasks', 'dossiers', 'account']);
  });

  it('adds Verwaltung for a principal with a taxonomy or mapping permission', () => {
    expect(keysFor(true, { roles: ['editor'], permissions: ['taxonomy.manage', 'venue.manage'] })).toEqual([
      'tasks',
      'dossiers',
      'admin',
      'account',
    ]);
  });

  it('adds Verwaltung for admin without a listed permission', () => {
    expect(keysFor(true, { roles: ['admin'] })).toContain('admin');
  });

  it('shows nothing without a session', () => {
    expect(keysFor(false)).toEqual([]);
  });

  it('keeps every bar entry in the navigation', () => {
    const keys = NAV_ITEMS.map((i) => i.key);
    expect(BOTTOM_BAR_KEYS.every((k) => keys.includes(k))).toBe(true);
  });

  it('points every entry at a route behind the session guard', () => {
    const shell = routes[0].children ?? [];
    for (const item of NAV_ITEMS) {
      const route = shell.find((r) => `/${r.path}` === item.path);
      expect(route?.canActivate).toBeDefined();
    }
  });
});
