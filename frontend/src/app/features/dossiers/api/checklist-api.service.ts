/** Typed client of the checklist endpoints of a dossier (M4 contract 5.3). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  ChecklistItemIn,
  ChecklistItemOut,
  ChecklistItemPatch,
  ChecklistOut,
} from '../model/checklist.models';

@Injectable({ providedIn: 'root' })
export class ChecklistApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  get(eventId: string): Observable<ChecklistOut> {
    return this.http.get<ChecklistOut>(`${this.base}/events/${eventId}/checklist`);
  }

  applyTemplate(eventId: string, templateSlug?: string): Observable<ChecklistOut> {
    return this.http.post<ChecklistOut>(
      `${this.base}/events/${eventId}/checklist/apply-template`,
      templateSlug ? { templateSlug } : {},
    );
  }

  add(eventId: string, body: ChecklistItemIn): Observable<ChecklistItemOut> {
    return this.http.post<ChecklistItemOut>(`${this.base}/events/${eventId}/checklist/items`, body);
  }

  patch(id: string, body: ChecklistItemPatch): Observable<ChecklistItemOut> {
    return this.http.patch<ChecklistItemOut>(`${this.base}/checklist-items/${id}`, body);
  }

  done(id: string, done: boolean): Observable<ChecklistItemOut> {
    return this.http.post<ChecklistItemOut>(`${this.base}/checklist-items/${id}/done`, { done });
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/checklist-items/${id}`);
  }
}
