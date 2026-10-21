/** Typed client of the format endpoints (M5 contract 4.4, 4.5). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import type { Observable } from 'rxjs';
import type { CloneOut } from '../../archive/model/archive.models';
import type { EventDto } from '../../dossiers/api/event.models';
import type {
  FormatCreate,
  FormatOut,
  FormatPage,
  FormatPatch,
  NewEditionIn,
  SaveAsFormatIn,
} from '../model/format.models';

@Injectable({ providedIn: 'root' })
export class FormatsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(query: { q?: string; organization?: string; limit?: number; offset?: number } = {}) {
    return this.http.get<FormatPage>(`${this.base}/formats`, { params: toParams(query) });
  }

  get(slug: string): Observable<FormatOut> {
    return this.http.get<FormatOut>(`${this.base}/formats/${slug}`);
  }

  create(body: FormatCreate): Observable<FormatOut> {
    return this.http.post<FormatOut>(`${this.base}/formats`, body);
  }

  patch(slug: string, body: FormatPatch): Observable<FormatOut> {
    return this.http.patch<FormatOut>(`${this.base}/formats/${slug}`, body);
  }

  createHowto(slug: string, fromEventId?: string): Observable<FormatOut> {
    return this.http.post<FormatOut>(`${this.base}/formats/${slug}/howto`, {
      ...(fromEventId && { fromEventId }),
    });
  }

  verify(slug: string): Observable<FormatOut> {
    return this.http.post<FormatOut>(`${this.base}/formats/${slug}/verify`, {});
  }

  newEdition(slug: string, body: NewEditionIn): Observable<CloneOut> {
    return this.http.post<CloneOut>(`${this.base}/formats/${slug}/new-edition`, body);
  }

  saveAsFormat(eventId: string, body: SaveAsFormatIn): Observable<FormatOut> {
    return this.http.post<FormatOut>(`${this.base}/events/${eventId}/save-as-format`, body);
  }

  setEventFormat(eventId: string, slug: string | null): Observable<EventDto> {
    return this.http.put<EventDto>(`${this.base}/events/${eventId}/format`, { slug });
  }
}
