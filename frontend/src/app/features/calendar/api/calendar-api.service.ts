/** Typed client of the calendar view of `GET /api/events` (M5 contract 7). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import type { Observable } from 'rxjs';
import type { CalendarOut, CalendarQuery } from '../model/calendar.models';

@Injectable({ providedIn: 'root' })
export class CalendarApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  range(query: CalendarQuery): Observable<CalendarOut> {
    return this.http.get<CalendarOut>(`${this.base}/events`, {
      params: toParams({ ...query, view: 'calendar' }),
    });
  }
}
