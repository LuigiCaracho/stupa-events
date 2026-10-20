/** Typed client of the document endpoints (howto, notes) with revisions, diff and server draft (M4 contract 5.2). */
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  DiffOut,
  DocumentDraft,
  DocumentIn,
  DocumentOut,
  DocumentPut,
  DocumentRevisionOut,
} from '../model/document.models';

const ifMatch = (rev: number): HttpHeaders => new HttpHeaders({ 'If-Match': `"${rev}"` });

@Injectable({ providedIn: 'root' })
export class DocumentsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(eventId: string, kind?: string): Observable<DocumentOut[]> {
    const params = kind ? new HttpParams().set('kind', kind) : new HttpParams();
    return this.http.get<DocumentOut[]>(`${this.base}/events/${eventId}/documents`, { params });
  }

  create(eventId: string, body: DocumentIn): Observable<DocumentOut> {
    return this.http.post<DocumentOut>(`${this.base}/events/${eventId}/documents`, body);
  }

  get(id: string): Observable<DocumentOut> {
    return this.http.get<DocumentOut>(`${this.base}/documents/${id}`);
  }

  put(id: string, rev: number, body: DocumentPut): Observable<DocumentOut> {
    return this.http.put<DocumentOut>(`${this.base}/documents/${id}`, body, {
      headers: ifMatch(rev),
    });
  }

  revisions(id: string): Observable<DocumentRevisionOut[]> {
    return this.http.get<DocumentRevisionOut[]>(`${this.base}/documents/${id}/revisions`);
  }

  revision(id: string, rev: number): Observable<DocumentOut> {
    return this.http.get<DocumentOut>(`${this.base}/documents/${id}/revisions/${rev}`);
  }

  diff(id: string, from: number, to: number): Observable<DiffOut> {
    const params = new HttpParams().set('from', from).set('to', to);
    return this.http.get<DiffOut>(`${this.base}/documents/${id}/diff`, { params });
  }

  getDraft(id: string): Observable<DocumentDraft> {
    return this.http.get<DocumentDraft>(`${this.base}/documents/${id}/draft`);
  }

  putDraft(id: string, baseRev: number, bodyMd: string): Observable<DocumentDraft> {
    return this.http.put<DocumentDraft>(
      `${this.base}/documents/${id}/draft`,
      { bodyMd },
      { headers: ifMatch(baseRev) },
    );
  }

  deleteDraft(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/documents/${id}/draft`);
  }
}
