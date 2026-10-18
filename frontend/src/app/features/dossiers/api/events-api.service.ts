/** Typed client of the internal event endpoints (`/api/events`, `/api/tasks`; M1 contract 4.3, M3 contract 5). */
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { type Observable, map } from 'rxjs';
import type {
  ActionBody,
  ActionName,
  DraftOut,
  RevisionDetail,
  RevisionOut,
} from './action.models';
import type { BoardOut, CardPage, EventQuery } from './board.models';
import type {
  Attachment,
  CategoryRef,
  EventCreate,
  EventDto,
  EventFields,
  EventPatch,
  GuardResult,
  OrgRef,
  Page,
  PosterMeta,
  PosterVariant,
  TransitionId,
  TransitionIn,
  VenueRef,
} from './event.models';
import type { TasksOut } from './task.models';

const items = <T>(body: T[] | Page<T>): T[] => (Array.isArray(body) ? body : body.items);

const ifMatch = (rev: number): HttpHeaders => new HttpHeaders({ 'If-Match': `"${rev}"` });

function queryParams(query: EventQuery): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === '' || value === false) continue;
    if (Array.isArray(value)) value.forEach((v) => (params = params.append(key, String(v))));
    else params = params.set(key, value === true ? '1' : String(value));
  }
  return params;
}

@Injectable({ providedIn: 'root' })
export class EventsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  listCards(query: EventQuery = {}): Observable<CardPage> {
    return this.http.get<CardPage>(`${this.base}/events`, {
      params: queryParams({ ...query, view: 'list' }),
    });
  }

  board(query: EventQuery = {}): Observable<BoardOut> {
    return this.http.get<BoardOut>(`${this.base}/events`, {
      params: queryParams({ ...query, view: 'board' }),
    });
  }

  tasks(): Observable<TasksOut> {
    return this.http.get<TasksOut>(`${this.base}/tasks`);
  }

  get(id: string): Observable<EventDto> {
    return this.http.get<EventDto>(`${this.base}/events/${id}`);
  }

  create(body: EventCreate): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events`, body);
  }

  /** Saves explicitly; `rev` is the version the edit started from and travels as `If-Match`. */
  patch(id: string, rev: number, body: EventPatch): Observable<EventDto> {
    return this.http.patch<EventDto>(`${this.base}/events/${id}`, body, { headers: ifMatch(rev) });
  }

  transition(
    id: string,
    transition: TransitionId,
    body: TransitionIn = {},
    rev?: number,
  ): Observable<EventDto> {
    const headers = rev === undefined ? undefined : ifMatch(rev);
    return this.http.post<EventDto>(`${this.base}/events/${id}/transitions/${transition}`, body, {
      headers,
    });
  }

  guards(id: string, transition: TransitionId): Observable<GuardResult> {
    return this.http.get<GuardResult>(`${this.base}/events/${id}/guards/${transition}`);
  }

  action(id: string, name: ActionName, body: ActionBody = {}, rev?: number): Observable<EventDto> {
    const headers = rev === undefined ? undefined : ifMatch(rev);
    return this.http.post<EventDto>(`${this.base}/events/${id}/actions/${name}`, body, { headers });
  }

  draft(id: string): Observable<DraftOut | null> {
    return this.http
      .get<DraftOut>(`${this.base}/events/${id}/draft`, { observe: 'response' })
      .pipe(map((res) => (res.status === 204 ? null : res.body)));
  }

  saveDraft(id: string, baseRev: number, fields: EventFields): Observable<DraftOut> {
    return this.http.put<DraftOut>(
      `${this.base}/events/${id}/draft`,
      { fields },
      { headers: ifMatch(baseRev) },
    );
  }

  discardDraft(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/events/${id}/draft`);
  }

  revisions(
    id: string,
    limit = 50,
    offset = 0,
    filter: { fieldClass?: string; minRev?: number } = {},
  ): Observable<Page<RevisionOut>> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (filter.fieldClass) params = params.set('fieldClass', filter.fieldClass);
    if (filter.minRev) params = params.set('minRev', filter.minRev);
    return this.http.get<Page<RevisionOut>>(`${this.base}/events/${id}/revisions`, { params });
  }

  revision(id: string, rev: number): Observable<RevisionDetail> {
    return this.http.get<RevisionDetail>(`${this.base}/events/${id}/revisions/${rev}`);
  }

  uploadPoster(id: string, file: File, meta: PosterMeta): Observable<Attachment> {
    const body = new FormData();
    body.append('file', file);
    body.append('altText', meta.altText);
    body.append('credit', meta.credit);
    body.append('rightsBasis', meta.rightsBasis);
    if (meta.personsDepicted !== undefined)
      body.append('personsDepicted', String(meta.personsDepicted));
    if (meta.consentNote) body.append('consentNote', meta.consentNote);
    return this.http.post<Attachment>(`${this.base}/events/${id}/poster`, body);
  }

  posterUrl(id: string, variant: PosterVariant): string {
    return `${this.base}/events/${id}/poster/file?variant=${variant}`;
  }

  organizations(): Observable<OrgRef[]> {
    return this.http
      .get<OrgRef[] | Page<OrgRef>>(`${this.base}/organizations?creatable=true`)
      .pipe(map(items));
  }

  categories(): Observable<CategoryRef[]> {
    return this.http
      .get<CategoryRef[] | Page<CategoryRef>>(`${this.base}/categories?tree=true`)
      .pipe(map(items));
  }

  venues(): Observable<VenueRef[]> {
    return this.http.get<VenueRef[] | Page<VenueRef>>(`${this.base}/venues`).pipe(map(items));
  }

  /** All organizations (not only the creatable ones), for filters and the assignment dialog. */
  allOrganizations(): Observable<OrgRef[]> {
    return this.http.get<OrgRef[] | Page<OrgRef>>(`${this.base}/organizations`).pipe(map(items));
  }
}
