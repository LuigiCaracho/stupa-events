import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { type ActivatedRouteSnapshot, Router, type RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { type Observable, firstValueFrom } from 'rxjs';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { adminLandingGuard } from './admin-tabs';

async function landing(me: { roles: string[]; permissions: string[] }): Promise<string> {
  TestBed.configureTestingModule({
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), provideLocationMock(createLocationMock())],
  });
  const result = TestBed.runInInjectionContext(() =>
    adminLandingGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  ) as Observable<UrlTree>;
  const pending = firstValueFrom(result);
  TestBed.inject(HttpTestingController).expectOne('/api/auth/me').flush({ sub: '1', groups: [], organizations: [], ...me });
  return TestBed.inject(Router).serializeUrl(await pending);
}

describe('adminLandingGuard', () => {
  it('lands an editor on the categories', async () => {
    expect(await landing({ roles: ['editor'], permissions: ['taxonomy.manage', 'venue.manage'] })).toBe('/verwaltung/kategorien');
  });

  it('lands a principal with venues only on the venues', async () => {
    expect(await landing({ roles: [], permissions: ['venue.manage'] })).toBe('/verwaltung/orte');
  });

  it('lands a principal with mappings only on the mappings', async () => {
    expect(await landing({ roles: [], permissions: ['admin.mappings'] })).toBe('/verwaltung/zuordnungen');
  });

  it('sends everybody else to /forbidden', async () => {
    expect(await landing({ roles: ['organizer'], permissions: ['event.edit'] })).toBe('/forbidden');
  });
});
