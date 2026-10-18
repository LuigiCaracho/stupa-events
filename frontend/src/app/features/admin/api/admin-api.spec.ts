import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MappingsApi } from './mappings-api.service';
import { SessionsApi } from './sessions-api.service';
import { TaxonomyApi } from './taxonomy-api.service';

describe('admin API services', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('talks to the taxonomy endpoints', () => {
    const api = TestBed.inject(TaxonomyApi);
    api.categories().subscribe();
    http.expectOne('/api/admin/categories').flush([]);
    api.createVenue({ slug: 'a', name: 'A' }).subscribe();
    expect(http.expectOne({ method: 'POST', url: '/api/admin/venues' }).request.body).toEqual({
      slug: 'a',
      name: 'A',
    });
    api.updateOrganization('o1', { trusted: true }).subscribe();
    expect(
      http.expectOne({ method: 'PATCH', url: '/api/admin/organizations/o1' }).request.body,
    ).toEqual({ trusted: true });
    api.organizations().subscribe();
    http.expectOne('/api/admin/organizations').flush([]);
    api.venues().subscribe();
    http.expectOne('/api/admin/venues').flush([]);
    api.createCategory({ slug: 'c', name: 'C' }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/admin/categories' }).flush({});
    api.updateCategory('c1', { name: 'D' }).subscribe();
    http.expectOne({ method: 'PATCH', url: '/api/admin/categories/c1' }).flush({});
    api.createOrganization({ slug: 'o', name: 'O' }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/admin/organizations' }).flush({});
    api.updateVenue('v1', { name: 'V' }).subscribe();
    http.expectOne({ method: 'PATCH', url: '/api/admin/venues/v1' }).flush({});
  });

  it('talks to the mapping endpoints', () => {
    const api = TestBed.inject(MappingsApi);
    api.list().subscribe();
    http.expectOne('/api/admin/group-mappings').flush([]);
    api.create({ oidcGroup: 'g', role: 'editor' }).subscribe();
    http.expectOne({ method: 'POST', url: '/api/admin/group-mappings' }).flush({});
    api.update('m1', { role: 'viewer', organizationId: 'o' }).subscribe();
    http.expectOne({ method: 'PATCH', url: '/api/admin/group-mappings/m1' }).flush({});
    api.remove('m1').subscribe();
    http.expectOne({ method: 'DELETE', url: '/api/admin/group-mappings/m1' }).flush(null);
    api.createDefaults().subscribe();
    http.expectOne({ method: 'POST', url: '/api/admin/group-mappings/defaults' }).flush([]);
    api.organizations().subscribe();
    http.expectOne('/api/organizations').flush([]);
    api.principals('events-admin').subscribe();
    http.expectOne('/api/admin/principals?group=events-admin&limit=200').flush({ items: [] });
  });

  it('posts both session revokes', () => {
    const api = TestBed.inject(SessionsApi);
    api.revokeOwn().subscribe();
    http.expectOne({ method: 'POST', url: '/api/auth/sessions/revoke' }).flush({ revoked: 1 });
    api.revokePrincipal('p1').subscribe();
    http
      .expectOne({ method: 'POST', url: '/api/admin/principals/p1/sessions/revoke' })
      .flush({ revoked: 3 });
  });
});
