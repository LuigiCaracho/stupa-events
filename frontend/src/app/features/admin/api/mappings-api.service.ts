/** Typed client of the group-mapping endpoints and the principal preview (M2 contract 2.4). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { OrgRef, Page } from '../../dossiers/api/event.models';
import type { Observable } from 'rxjs';
import type { AdminPrincipal, GroupMapping, MappingCreate, MappingPatch } from './admin.models';

@Injectable({ providedIn: 'root' })
export class MappingsApi {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);
  private readonly base = `${this.root}/admin`;

  list(): Observable<GroupMapping[]> {
    return this.http.get<GroupMapping[]>(`${this.base}/group-mappings`);
  }

  create(body: MappingCreate): Observable<GroupMapping> {
    return this.http.post<GroupMapping>(`${this.base}/group-mappings`, body);
  }

  update(id: string, body: MappingPatch): Observable<GroupMapping> {
    return this.http.patch<GroupMapping>(`${this.base}/group-mappings/${id}`, body);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/group-mappings/${id}`);
  }

  organizations(): Observable<OrgRef[]> {
    return this.http.get<OrgRef[]>(`${this.root}/organizations`);
  }

  createDefaults(): Observable<GroupMapping[]> {
    return this.http.post<GroupMapping[]>(`${this.base}/group-mappings/defaults`, {});
  }

  principals(group: string): Observable<Page<AdminPrincipal>> {
    const params = new HttpParams().set('group', group).set('limit', 200);
    return this.http.get<Page<AdminPrincipal>>(`${this.base}/principals`, { params });
  }
}
