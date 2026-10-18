import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { type ActivatedRouteSnapshot, type RouterStateSnapshot, Router, UrlTree, provideRouter } from '@angular/router';
import { type Observable, firstValueFrom } from 'rxjs';
import { createLocationMock, provideLocationMock } from '../../../testing/location-mock';
import { permissionGuard } from './permission.guard';

async function run(permissions: string[], me: { roles: string[]; permissions: string[] }) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      provideLocationMock(createLocationMock()),
    ],
  });
  const result = TestBed.runInInjectionContext(() =>
    permissionGuard(...permissions)({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
  ) as Observable<boolean | UrlTree>;
  const pending = firstValueFrom(result);
  TestBed.inject(HttpTestingController)
    .expectOne('/api/auth/me')
    .flush({ sub: '1', groups: [], organizations: [], ...me });
  return pending;
}

describe('permissionGuard', () => {
  it('lets a principal with one of the permissions pass', async () => {
    expect(await run(['taxonomy.manage', 'admin.mappings'], { roles: ['editor'], permissions: ['taxonomy.manage'] })).toBe(true);
  });

  it('lets admin pass without a listed permission', async () => {
    expect(await run(['admin.mappings'], { roles: ['admin'], permissions: [] })).toBe(true);
  });

  it('redirects everybody else to /forbidden', async () => {
    const result = await run(['admin.mappings'], { roles: ['organizer'], permissions: ['event.edit'] });
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/forbidden');
  });
});
