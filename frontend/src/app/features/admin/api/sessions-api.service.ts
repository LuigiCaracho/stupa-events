/** Typed client of the session revoke endpoints: own other sessions and, for admins, all of a person (M2 contract 2.5). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type { RevokeResult } from './admin.models';

@Injectable({ providedIn: 'root' })
export class SessionsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  revokeOwn(): Observable<RevokeResult> {
    return this.http.post<RevokeResult>(`${this.base}/auth/sessions/revoke`, {});
  }

  revokePrincipal(principalId: string): Observable<RevokeResult> {
    return this.http.post<RevokeResult>(`${this.base}/admin/principals/${principalId}/sessions/revoke`, {});
  }
}
