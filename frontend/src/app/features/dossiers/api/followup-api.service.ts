/** Typed client of the follow-up of a dossier: result, "Anleitung geprüft", location, facts (M5 contract 3). */
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type { OutcomeIn } from '../model/followup.models';
import type { EventDto } from './event.models';

const ifMatch = (rev: number): HttpHeaders => new HttpHeaders({ 'If-Match': `"${rev}"` });

@Injectable({ providedIn: 'root' })
export class FollowupApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  putOutcome(id: string, rev: number, body: OutcomeIn): Observable<EventDto> {
    return this.http.put<EventDto>(`${this.base}/events/${id}/outcome`, body, {
      headers: ifMatch(rev),
    });
  }

  verifyHowto(id: string): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events/${id}/actions/verify-howto`, {});
  }

  unverifyHowto(id: string): Observable<EventDto> {
    return this.http.delete<EventDto>(`${this.base}/events/${id}/actions/verify-howto`);
  }

  confirmLocation(id: string, precision: 'exact' | 'building'): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events/${id}/actions/confirm-location`, {
      precision,
    });
  }

  putFacts(id: string, rev: number, facts: Record<string, unknown>): Observable<EventDto> {
    return this.http.put<EventDto>(`${this.base}/events/${id}/facts`, facts, {
      headers: ifMatch(rev),
    });
  }
}
