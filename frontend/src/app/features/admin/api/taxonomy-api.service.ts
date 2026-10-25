/** Typed client of the taxonomy admin endpoints: categories, venues and organizations (M2 contract 2.3). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  AdminCategory,
  AdminOrganization,
  AdminVenue,
  CategoryWrite,
  OrganizationWrite,
  VenueGeocode,
  VenueWrite,
} from './admin.models';

@Injectable({ providedIn: 'root' })
export class TaxonomyApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/admin`;

  categories(): Observable<AdminCategory[]> {
    return this.http.get<AdminCategory[]>(`${this.base}/categories`);
  }

  createCategory(body: CategoryWrite): Observable<AdminCategory> {
    return this.http.post<AdminCategory>(`${this.base}/categories`, body);
  }

  updateCategory(id: string, body: CategoryWrite): Observable<AdminCategory> {
    return this.http.patch<AdminCategory>(`${this.base}/categories/${id}`, body);
  }

  venues(): Observable<AdminVenue[]> {
    return this.http.get<AdminVenue[]>(`${this.base}/venues`);
  }

  createVenue(body: VenueWrite): Observable<AdminVenue> {
    return this.http.post<AdminVenue>(`${this.base}/venues`, body);
  }

  updateVenue(id: string, body: VenueWrite): Observable<AdminVenue> {
    return this.http.patch<AdminVenue>(`${this.base}/venues/${id}`, body);
  }

  geocodeVenue(id: string): Observable<VenueGeocode> {
    return this.http.post<VenueGeocode>(`${this.base}/venues/${id}/geocode`, {});
  }

  organizations(): Observable<AdminOrganization[]> {
    return this.http.get<AdminOrganization[]>(`${this.base}/organizations`);
  }

  createOrganization(body: OrganizationWrite): Observable<AdminOrganization> {
    return this.http.post<AdminOrganization>(`${this.base}/organizations`, body);
  }

  updateOrganization(id: string, body: OrganizationWrite): Observable<AdminOrganization> {
    return this.http.patch<AdminOrganization>(`${this.base}/organizations/${id}`, body);
  }
}
