/** Typed client of the in-app notifications and the notification preferences (M4 contract 5.7). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { type Observable, map } from 'rxjs';
import type {
  NotificationOut,
  NotificationPage,
  NotificationPref,
  NotificationPrefIn,
} from '../dossiers/model/notification.models';

@Injectable({ providedIn: 'root' })
export class NotificationsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(unread = false, limit = 30, cursor: string | null = null): Observable<NotificationPage> {
    let params = new HttpParams().set('limit', limit);
    if (unread) params = params.set('unread', true);
    if (cursor) params = params.set('cursor', cursor);
    return this.http
      .get<NotificationOut[] | NotificationPage>(`${this.base}/notifications`, { params })
      .pipe(map((body) => (Array.isArray(body) ? { items: body, nextCursor: null } : body)));
  }

  unreadCount(): Observable<number> {
    return this.http
      .get<{ count: number }>(`${this.base}/notifications/unread-count`)
      .pipe(map((body) => body.count));
  }

  markRead(id: string): Observable<void> {
    return this.http.post<void>(`${this.base}/notifications/${id}/read`, {});
  }

  markAllRead(): Observable<void> {
    return this.http.post<void>(`${this.base}/notifications/read-all`, {});
  }

  prefs(): Observable<NotificationPref[]> {
    return this.http
      .get<{ items: NotificationPref[] }>(`${this.base}/account/notification-prefs`)
      .pipe(map((body) => body.items));
  }

  savePrefs(items: NotificationPrefIn[]): Observable<NotificationPref[]> {
    return this.http
      .put<{ items: NotificationPref[] }>(`${this.base}/account/notification-prefs`, { items })
      .pipe(map((body) => body.items));
  }
}
