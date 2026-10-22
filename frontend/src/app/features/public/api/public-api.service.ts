/** Typed client of the public site API (B1 contract 2.2 to 2.7): root-relative `/api/public/...` URLs, no session needed. */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import type { Observable } from 'rxjs';
import type {
  PublicArchiveOut,
  PublicCalendarOut,
  PublicCategoryOut,
  PublicEventDetail,
  PublicSearchOut,
  PublicSearchQuery,
  PublicTodayOut,
} from '../model/public.models';

export interface ArchiveQuery {
  year?: number;
  category?: string;
  limit?: number;
  cursor?: string | null;
}

@Injectable({ providedIn: 'root' })
export class PublicApi {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/public`;

  events(query: PublicSearchQuery): Observable<PublicSearchOut> {
    return this.http.get<PublicSearchOut>(`${this.base}/events`, { params: toParams(query) });
  }

  event(slug: string): Observable<PublicEventDetail> {
    return this.http.get<PublicEventDetail>(`${this.base}/events/${encodeURIComponent(slug)}`);
  }

  today(): Observable<PublicTodayOut> {
    return this.http.get<PublicTodayOut>(`${this.base}/today`);
  }

  categories(): Observable<PublicCategoryOut[]> {
    return this.http.get<PublicCategoryOut[]>(`${this.base}/categories`);
  }

  calendar(month: string, category?: string): Observable<PublicCalendarOut> {
    return this.http.get<PublicCalendarOut>(`${this.base}/calendar`, {
      params: toParams({ month, category }),
    });
  }

  archive(query: ArchiveQuery): Observable<PublicArchiveOut> {
    return this.http.get<PublicArchiveOut>(`${this.base}/archive`, { params: toParams(query) });
  }
}
