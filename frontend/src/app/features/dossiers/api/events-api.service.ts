/** Typed client of the internal event endpoints (`/api/events`, M1 contract 4.3). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { type Observable, map } from 'rxjs';
import type {
  Attachment,
  CategoryRef,
  EventCreate,
  EventDto,
  EventPatch,
  EventQuery,
  GuardResult,
  OrgRef,
  Page,
  PosterMeta,
  PosterVariant,
  TransitionId,
} from './event.models';

const items = <T>(body: T[] | Page<T>): T[] => (Array.isArray(body) ? body : body.items);

@Injectable({ providedIn: 'root' })
export class EventsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(query: EventQuery = {}): Observable<Page<EventDto>> {
    const params = new HttpParams({
      fromObject: Object.fromEntries(
        Object.entries(query)
          .filter(([, v]) => v !== undefined && v !== '')
          .map(([k, v]) => [k, String(v)]),
      ),
    });
    return this.http.get<Page<EventDto>>(`${this.base}/events`, { params });
  }

  get(id: string): Observable<EventDto> {
    return this.http.get<EventDto>(`${this.base}/events/${id}`);
  }

  create(body: EventCreate): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events`, body);
  }

  patch(id: string, body: EventPatch): Observable<EventDto> {
    return this.http.patch<EventDto>(`${this.base}/events/${id}`, body);
  }

  transition(id: string, transition: TransitionId, note?: string): Observable<EventDto> {
    return this.http.post<EventDto>(
      `${this.base}/events/${id}/transitions/${transition}`,
      note ? { note } : {},
    );
  }

  guards(id: string, transition: TransitionId): Observable<GuardResult> {
    return this.http.get<GuardResult>(`${this.base}/events/${id}/guards/${transition}`);
  }

  uploadPoster(id: string, file: File, meta: PosterMeta): Observable<Attachment> {
    const body = new FormData();
    body.append('file', file);
    body.append('altText', meta.altText);
    body.append('credit', meta.credit);
    body.append('rightsBasis', meta.rightsBasis);
    return this.http.post<Attachment>(`${this.base}/events/${id}/poster`, body);
  }

  imageException(id: string, reason: string): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events/${id}/image-exception`, { reason });
  }

  posterUrl(id: string, variant: PosterVariant): string {
    return `${this.base}/events/${id}/poster/file?variant=${variant}`;
  }

  organizations(): Observable<OrgRef[]> {
    return this.http.get<OrgRef[] | Page<OrgRef>>(`${this.base}/organizations?creatable=true`).pipe(map(items));
  }

  categories(): Observable<CategoryRef[]> {
    return this.http.get<CategoryRef[] | Page<CategoryRef>>(`${this.base}/categories?tree=true`).pipe(map(items));
  }
}
