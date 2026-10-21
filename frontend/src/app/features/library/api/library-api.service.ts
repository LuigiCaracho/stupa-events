/** Typed client of the library endpoints (M5 contract 5). */
import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_BASE_URL } from '@core/api/api.config';
import { toParams } from '@core/api/query-params';
import type { Observable } from 'rxjs';
import type { DocumentOut } from '../../dossiers/model/document.models';
import type { LibraryPage, LibraryQuery } from '../model/library.models';

@Injectable({ providedIn: 'root' })
export class LibraryApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  list(query: LibraryQuery = {}): Observable<LibraryPage> {
    return this.http.get<LibraryPage>(`${this.base}/library`, { params: toParams(query) });
  }

  document(id: string): Observable<DocumentOut> {
    return this.http.get<DocumentOut>(`${this.base}/documents/${id}`);
  }

  adopt(documentId: string, eventId: string): Observable<DocumentOut> {
    return this.http.post<DocumentOut>(`${this.base}/library/documents/${documentId}/adopt`, {
      eventId,
    });
  }

  downloadUrl(attachmentId: string): string {
    return `${this.base}/attachments/${attachmentId}/download`;
  }

  previewUrl(attachmentId: string): string {
    return `${this.base}/attachments/${attachmentId}/preview`;
  }
}
