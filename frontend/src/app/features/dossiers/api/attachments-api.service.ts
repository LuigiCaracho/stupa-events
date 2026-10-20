/** Typed client of the attachment, quote and counter endpoints of a dossier (M4 contract 5.1, 5.8). */
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import type { Observable } from 'rxjs';
import type {
  AttachmentOut,
  AttachmentPatch,
  AttachmentUpload,
  DossierCounts,
  QuoteIn,
  QuotesOut,
} from '../model/attachment.models';

function uploadForm(upload: AttachmentUpload): FormData {
  const form = new FormData();
  const { file, ...fields } = upload;
  form.set('file', file, file.name);
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== undefined && value !== '') form.set(key, String(value));
  });
  return form;
}

@Injectable({ providedIn: 'root' })
export class AttachmentsApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(eventId: string, includeRetired = false): Observable<AttachmentOut[]> {
    const params = new HttpParams().set('includeRetired', includeRetired);
    return this.http.get<AttachmentOut[]>(`${this.base}/events/${eventId}/attachments`, { params });
  }

  counts(eventId: string): Observable<DossierCounts> {
    return this.http.get<DossierCounts>(`${this.base}/events/${eventId}/dossier-counts`);
  }

  upload(eventId: string, upload: AttachmentUpload): Observable<AttachmentOut> {
    return this.http.post<AttachmentOut>(
      `${this.base}/events/${eventId}/attachments`,
      uploadForm(upload),
    );
  }

  replace(id: string, upload: AttachmentUpload): Observable<AttachmentOut> {
    return this.http.post<AttachmentOut>(
      `${this.base}/attachments/${id}/replace`,
      uploadForm(upload),
    );
  }

  patch(id: string, body: AttachmentPatch): Observable<AttachmentOut> {
    return this.http.patch<AttachmentOut>(`${this.base}/attachments/${id}`, body);
  }

  retire(id: string): Observable<void> {
    return this.http.post<void>(`${this.base}/attachments/${id}/retire`, {});
  }

  downloadUrl(id: string): string {
    return `${this.base}/attachments/${id}/download`;
  }

  previewUrl(id: string): string {
    return `${this.base}/attachments/${id}/preview`;
  }

  quotes(eventId: string): Observable<QuotesOut> {
    return this.http.get<QuotesOut>(`${this.base}/events/${eventId}/quotes`);
  }

  addQuote(eventId: string, body: QuoteIn): Observable<unknown> {
    return this.http.post(`${this.base}/events/${eventId}/quotes`, body);
  }

  selectQuote(id: string): Observable<unknown> {
    return this.http.post(`${this.base}/quotes/${id}/select`, {});
  }

  removeQuote(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/quotes/${id}`);
  }
}
