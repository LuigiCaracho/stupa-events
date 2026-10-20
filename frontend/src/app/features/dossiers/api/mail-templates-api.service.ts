/** Typed client of the mail template facade of a dossier (M4 contract 5.6). */
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  MailTemplateOut,
  MailTemplatePut,
  MailTemplateSummary,
  PlaceholderOut,
  RenderedMail,
} from '../model/document.models';

@Injectable({ providedIn: 'root' })
export class MailTemplatesApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(eventId: string): Observable<MailTemplateSummary[]> {
    return this.http.get<MailTemplateSummary[]>(`${this.base}/events/${eventId}/mail-templates`);
  }

  get(eventId: string, id: string): Observable<MailTemplateOut> {
    return this.http.get<MailTemplateOut>(`${this.base}/events/${eventId}/mail-templates/${id}`);
  }

  /** `id = 'new'` creates a template; otherwise `rev` travels as `If-Match`. */
  put(
    eventId: string,
    id: string,
    rev: number,
    body: MailTemplatePut,
  ): Observable<MailTemplateOut> {
    return this.http.put<MailTemplateOut>(
      `${this.base}/events/${eventId}/mail-templates/${id}`,
      body,
      {
        headers: new HttpHeaders(id === 'new' ? {} : { 'If-Match': `"${rev}"` }),
      },
    );
  }

  preview(
    eventId: string,
    id: string,
    draft: { subject?: string; bodyMd?: string },
  ): Observable<RenderedMail> {
    return this.http.post<RenderedMail>(
      `${this.base}/events/${eventId}/mail-templates/${id}/render-preview`,
      draft,
    );
  }

  placeholders(): Observable<PlaceholderOut[]> {
    return this.http.get<PlaceholderOut[]>(`${this.base}/mail-template-placeholders`);
  }
}
