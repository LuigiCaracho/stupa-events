/**
 * Typed client of the subscription API (B3 contract 3.1 to 3.4). No call here sends credentials or a cookie: the
 * tokens of the manage routes travel in the `X-Subscription-Token` header, never in a query string.
 */
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  ConfirmPreviewOut,
  MeOut,
  MeUpdate,
  QuestionnaireOut,
  RotatedIcsOut,
  SubscribeIn,
  SubscribeOut,
} from '../model/subscriptions.models';

const TOKEN_HEADER = 'X-Subscription-Token';

@Injectable({ providedIn: 'root' })
export class SubscriptionsApi {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);
  private readonly base = `${this.root}/public/subscriptions`;
  private readonly options = { withCredentials: false };

  questions(): Observable<QuestionnaireOut> {
    return this.http.get<QuestionnaireOut>(`${this.root}/public/getstarted/questions`, this.options);
  }

  subscribe(body: SubscribeIn): Observable<SubscribeOut> {
    return this.http.post<SubscribeOut>(this.base, body, this.options);
  }

  confirmPreview(token: string): Observable<ConfirmPreviewOut> {
    return this.http.post<ConfirmPreviewOut>(`${this.base}/confirm/preview`, { token }, this.options);
  }

  confirm(token: string): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.base}/confirm`, { token }, this.options);
  }

  requestManageLink(email: string, altcha: string): Observable<object> {
    return this.http.post<object>(`${this.base}/manage-link`, { email, altcha }, this.options);
  }

  me(token: string): Observable<MeOut> {
    return this.http.get<MeOut>(`${this.base}/me`, this.withToken(token));
  }

  updateMe(token: string, body: MeUpdate): Observable<MeOut> {
    return this.http.put<MeOut>(`${this.base}/me`, body, this.withToken(token));
  }

  rotateIcsToken(token: string): Observable<RotatedIcsOut> {
    return this.http.post<RotatedIcsOut>(`${this.base}/me/ics-token`, {}, this.withToken(token));
  }

  deleteMe(token: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/me`, this.withToken(token));
  }

  private withToken(token: string): { headers: HttpHeaders; withCredentials: false } {
    return { headers: new HttpHeaders({ [TOKEN_HEADER]: token }), withCredentials: false };
  }
}
