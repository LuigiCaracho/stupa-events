/** Typed client of the internal event endpoints (`/api/events`; M5b contract 7). */
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import { type Observable, map } from 'rxjs';
import type {
  CancelBody,
  DraftOut,
  PostponeBody,
  ReinstateBody,
  RevertBody,
  RevisionDetail,
  RevisionOut,
} from './action.models';
import type { CardPage, EventQuery } from './card.models';
import type {
  Attachment,
  CategoryRef,
  EventCreate,
  EventDto,
  EventFields,
  EventPatch,
  HintsOut,
  OrgRef,
  Page,
  PosterMeta,
  PosterVariant,
  VenueRef,
} from './event.models';

const items = <T>(body: T[] | Page<T>): T[] => (Array.isArray(body) ? body : body.items);

const ifMatch = (rev: number): HttpHeaders => new HttpHeaders({ 'If-Match': `"${rev}"` });

@Injectable({ providedIn: 'root' })
export class EventsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  listCards(query: EventQuery = {}): Observable<CardPage> {
    return this.http.get<CardPage>(`${this.base}/events`, {
      params: toParams({ ...query, view: 'list' }),
    });
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

  /** The lifecycle calls answer the dossier; `rev` travels as `If-Match`. */
  publish(id: string, rev: number): Observable<EventDto> {
    return this.lifecycle(id, 'publish', {}, rev);
  }

  unpublish(id: string, rev: number): Observable<EventDto> {
    return this.lifecycle(id, 'unpublish', {}, rev);
  }

  archive(id: string, rev: number): Observable<EventDto> {
    return this.lifecycle(id, 'archive', {}, rev);
  }

  restore(id: string, rev: number): Observable<EventDto> {
    return this.lifecycle(id, 'restore', {}, rev);
  }

  cancel(id: string, rev: number, body: CancelBody): Observable<EventDto> {
    return this.lifecycle(id, 'cancel', body, rev);
  }

  postpone(id: string, rev: number, body: PostponeBody): Observable<EventDto> {
    return this.lifecycle(id, 'postpone', body, rev);
  }

  reinstate(id: string, rev: number, body: ReinstateBody = {}): Observable<EventDto> {
    return this.lifecycle(id, 'reinstate', body, rev);
  }

  revert(id: string, rev: number, body: RevertBody): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events/${id}/actions/revert-revision`, body, {
      headers: ifMatch(rev),
    });
  }

  hints(id: string): Observable<HintsOut> {
    return this.http.get<HintsOut>(`${this.base}/events/${id}/hints`);
  }

  private lifecycle(
    id: string,
    name: 'publish' | 'unpublish' | 'archive' | 'restore' | 'cancel' | 'postpone' | 'reinstate',
    body: object,
    rev: number,
  ): Observable<EventDto> {
    return this.http.post<EventDto>(`${this.base}/events/${id}/${name}`, body, {
      headers: ifMatch(rev),
    });
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
  ): Observable<Page<RevisionOut>> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<Page<RevisionOut>>(`${this.base}/events/${id}/revisions`, { params });
  }

  revision(id: string, rev: number): Observable<RevisionDetail> {
    return this.http.get<RevisionDetail>(`${this.base}/events/${id}/revisions/${rev}`);
  }

  uploadPoster(id: string, file: File, meta: PosterMeta): Observable<Attachment> {
    const body = new FormData();
    body.append('file', file);
    if (meta.altText) body.append('altText', meta.altText);
    if (meta.credit) body.append('credit', meta.credit);
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

  /** All organizations (not only the creatable ones), for the filters. */
  allOrganizations(): Observable<OrgRef[]> {
    return this.http.get<OrgRef[] | Page<OrgRef>>(`${this.base}/organizations`).pipe(map(items));
  }
}
