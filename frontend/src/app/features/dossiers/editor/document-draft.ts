/**
 * Autosave of a document text against `PUT /documents/{id}/draft` (contract 5.2, 6.2): every 15 s, only when the text
 * changed, retried only after network and 5xx errors. A 4xx stops the autosave and shows the failed state; the text
 * stays in the local copy either way. A draft creates no revision and no audit entry.
 */
import { DestroyRef, NgZone, inject, signal } from '@angular/core';
import { problemOf } from '@core/api/problem';
import type { DocumentsApi } from '../api/documents-api.service';
import { clearLocalCopy, writeLocalCopy } from './local-copy';

export type DraftStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'failed';

export const DRAFT_INTERVAL_MS = 15_000;

export interface DraftTarget {
  documentId: string;
  baseRev: number;
}

export class DocumentDraft {
  readonly status = signal<DraftStatus>('idle');
  private text: string | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private stopped = false;

  constructor(
    private readonly api: DocumentsApi,
    private readonly target: () => DraftTarget | null,
    private readonly docKey: () => string,
    destroyRef: DestroyRef,
  ) {
    // Outside the zone, so a pending timer never keeps `whenStable` waiting.
    this.timer = inject(NgZone).runOutsideAngular(() =>
      setInterval(() => this.flush(), DRAFT_INTERVAL_MS),
    );
    destroyRef.onDestroy(() => this.stop());
  }

  change(text: string): void {
    this.text = text;
    this.stopped = false;
    this.status.set('dirty');
    writeLocalCopy(this.docKey(), text);
  }

  flush(): void {
    const target = this.target();
    if (this.text === null || !target || this.stopped || this.status() === 'saving') return;
    const sent = this.text;
    this.status.set('saving');
    this.api.putDraft(target.documentId, target.baseRev, sent).subscribe({
      next: () => {
        if (this.text === sent) this.text = null;
        this.status.set(this.text === null ? 'saved' : 'dirty');
      },
      error: (err: unknown) => {
        const { status } = problemOf(err);
        this.stopped = status !== 0 && status < 500;
        this.status.set(this.stopped ? 'failed' : 'dirty');
      },
    });
  }

  discard(): void {
    this.text = null;
    this.status.set('idle');
    clearLocalCopy(this.docKey());
    const target = this.target();
    if (target) this.api.deleteDraft(target.documentId).subscribe({ error: () => undefined });
  }

  settle(): void {
    this.text = null;
    this.status.set('idle');
    clearLocalCopy(this.docKey());
  }

  get pending(): boolean {
    return this.text !== null;
  }

  private stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
