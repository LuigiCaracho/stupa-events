/** Typed client of search, templates, cloning and the archive read path (M5 contract 4.1 to 4.3, 6). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import type { Observable } from 'rxjs';
import type {
  ArchiveEventOut,
  ClonePreview,
  CloneIn,
  CloneOut,
  LastTime,
  SearchOut,
  SearchQuery,
  TemplatePage,
  TemplateQuery,
} from '../model/archive.models';

@Injectable({ providedIn: 'root' })
export class ArchiveApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  event(id: string): Observable<ArchiveEventOut> {
    return this.http.get<ArchiveEventOut>(`${this.base}/archive/${id}`);
  }

  search(query: SearchQuery): Observable<SearchOut> {
    return this.http.get<SearchOut>(`${this.base}/search`, { params: toParams(query) });
  }

  templates(query: TemplateQuery): Observable<TemplatePage> {
    return this.http.get<TemplatePage>(`${this.base}/templates`, { params: toParams(query) });
  }

  clonePreview(id: string, organizationId?: string): Observable<ClonePreview> {
    let params = new HttpParams();
    if (organizationId) params = params.set('organizationId', organizationId);
    return this.http.get<ClonePreview>(`${this.base}/events/${id}/clone-preview`, { params });
  }

  clone(id: string, body: CloneIn): Observable<CloneOut> {
    return this.http.post<CloneOut>(`${this.base}/events/${id}/clone`, body);
  }

  /** `null` when there is no earlier edition ("Noch keine Ausgabe"). */
  lastTime(id: string): Observable<LastTime | null> {
    return this.http.get<LastTime | null>(`${this.base}/events/${id}/last-time`);
  }
}
