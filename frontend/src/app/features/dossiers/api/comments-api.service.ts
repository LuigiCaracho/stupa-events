/** Typed client of the comment endpoints of a dossier (M4 contract 5.5). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type { CommentIn, CommentOut, CommentThread } from '../model/comment.models';

@Injectable({ providedIn: 'root' })
export class CommentsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(eventId: string, openOnly = false): Observable<CommentThread[]> {
    const params = openOnly ? new HttpParams().set('open', true) : new HttpParams();
    return this.http.get<CommentThread[]>(`${this.base}/events/${eventId}/comments`, { params });
  }

  add(eventId: string, body: CommentIn): Observable<CommentOut> {
    return this.http.post<CommentOut>(`${this.base}/events/${eventId}/comments`, body);
  }

  resolve(id: string): Observable<CommentOut> {
    return this.http.post<CommentOut>(`${this.base}/comments/${id}/resolve`, {});
  }

  reopen(id: string): Observable<CommentOut> {
    return this.http.post<CommentOut>(`${this.base}/comments/${id}/reopen`, {});
  }
}
