/**
 * The autosave of the dossier form (E21). It collects the changes of one person, sends them as a draft
 * (`PUT .../draft`) 15 s after the first unsent change and then every 15 s while changes remain, saves them for good
 * on request (`PATCH`, which also drops the draft) and applies them by itself after 30 minutes without input, but only
 * in `idea` and `planning`. Offline, the text waits in `localStorage` and goes out when the connection is back.
 * A stale draft or a 409 raises the conflict handler; nothing is overwritten. Only network and 5xx errors retry by
 * themselves; a 4xx (locked field, right, size) stops, is reported once and keeps the draft until the next change.
 */
import { type Signal, computed, signal } from '@angular/core';
import { problemOf } from '@core/api/problem';
import { type Observable, catchError, map, of, tap, throwError } from 'rxjs';
import type { DraftOut } from '../api/action.models';
import type { EventDto, EventFields } from '../api/event.models';
import type { EventsApi } from '../api/events-api.service';

export const AUTOSAVE_MS = 15_000;
export const IDLE_APPLY_MS = 30 * 60_000;
const IDLE_STATES: readonly string[] = ['idea', 'planning'];

export type SaveStatus = 'idle' | 'saved' | 'saving' | 'unsaved' | 'offline' | 'conflict' | 'error';

export type Restored =
  { kind: 'none' } | { kind: 'restored'; draft: DraftOut } | { kind: 'stale'; draft: DraftOut };

interface Buffered {
  baseRev: number;
  fields: EventFields;
  at: string;
}

export interface AutosaveDeps {
  api: EventsApi;
  event: Signal<EventDto | null>;
  sub: () => string | null;
  storage?: () => Storage | null;
  /** The idle timer saved the draft for good. */
  onApplied: (event: EventDto) => void;
  /** A save met a newer version; `current` is that version when the server sent it. */
  onConflict: (current: EventDto | null) => void;
  onOffline: () => void;
  onError: (err: unknown) => void;
}

const same = (a: EventFields, b: EventFields): boolean => JSON.stringify(a) === JSON.stringify(b);
const empty = (fields: EventFields): boolean => Object.keys(fields).length === 0;

export class DraftAutosave {
  readonly status = signal<SaveStatus>('idle');
  readonly savedAt = signal<Date | null>(null);
  readonly fields = signal<EventFields>({});
  readonly dirty = computed(() => !empty(this.fields()));
  private readonly sent = signal<EventFields>({});
  /** Changes that no draft on the server holds yet: leaving the page would lose them. */
  readonly unsent = computed(() => this.dirty() && !same(this.fields(), this.sent()));

  private inflight = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly deps: AutosaveDeps) {}

  /** The form reports its complete set of changes against the event. */
  change(fields: EventFields): void {
    if (same(fields, this.fields())) return;
    this.fields.set(fields);
    this.restartIdle();
    if (empty(fields)) {
      this.stopTimer();
      if (!empty(this.sent())) this.drop();
      this.status.set(this.savedAt() ? 'saved' : 'idle');
      return;
    }
    if (this.status() !== 'offline' && this.status() !== 'conflict') this.status.set('unsaved');
    if (!this.timer && !same(fields, this.sent())) this.schedule();
  }

  /** Sends the draft now (also the retry after the connection came back). */
  flush(): void {
    const event = this.deps.event();
    const fields = this.fields();
    if (!event || empty(fields) || same(fields, this.sent()) || this.inflight) return;
    this.inflight = true;
    this.status.set('saving');
    this.deps.api.saveDraft(event.id, event.rev, fields).subscribe({
      next: () => this.flushed(fields),
      error: (err: unknown) => this.flushFailed(err, event, fields),
    });
  }

  /** Saves explicitly: `PATCH` with the changes, which also drops the draft on the server. */
  save(note?: string): Observable<EventDto> {
    const event = this.deps.event();
    if (!event) return throwError(() => new Error('no event'));
    this.stopTimer();
    this.status.set('saving');
    return this.deps.api
      .patch(event.id, event.rev, { ...this.fields(), ...(note && { note }) })
      .pipe(
        tap(() => this.cleared(true, true)),
        catchError((err: unknown) => {
          this.status.set(this.dirty() ? 'unsaved' : 'idle');
          if (problemOf(err).code === 'conflict') this.conflicted(err);
          return throwError(() => err);
        }),
      );
  }

  /** Throws the changes away, here and on the server. */
  discard(): void {
    const event = this.deps.event();
    this.cleared(false, true);
    if (event) this.deps.api.discardDraft(event.id).subscribe({ error: () => undefined });
  }

  /** Forgets the local state when a dossier opens; the offline text in storage and the server draft stay. */
  reset(): void {
    this.cleared(false, false);
  }

  /** Looks for a draft when the dossier opens: the server's and the offline buffer, the newer one wins. */
  restore(event: EventDto): Observable<Restored> {
    return this.deps.api.draft(event.id).pipe(
      catchError(() => of(null)),
      map((server) => {
        const buffered = this.readBuffer(event.id);
        const useBuffer =
          !!buffered && (!server || Date.parse(buffered.at) > Date.parse(server.updatedAt));
        const draft: DraftOut | null = useBuffer
          ? { baseRev: buffered.baseRev, fields: buffered.fields, updatedAt: buffered.at }
          : server;
        if (!draft || empty(draft.fields)) return { kind: 'none' } as const;
        if (draft.baseRev < event.rev) return { kind: 'stale', draft } as const;
        this.fields.set(draft.fields);
        this.sent.set(useBuffer ? {} : draft.fields);
        this.status.set(useBuffer ? 'unsaved' : 'saved');
        this.savedAt.set(new Date(draft.updatedAt));
        if (useBuffer) this.schedule();
        return { kind: 'restored', draft } as const;
      }),
    );
  }

  destroy(): void {
    this.stopTimer();
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = null;
  }

  private flushed(sent: EventFields): void {
    this.inflight = false;
    this.sent.set(sent);
    this.removeBuffer();
    if (same(this.fields(), sent)) {
      this.status.set('saved');
      this.savedAt.set(new Date());
    } else {
      this.status.set('unsaved');
      this.schedule();
    }
  }

  private flushFailed(err: unknown, event: EventDto, fields: EventFields): void {
    this.inflight = false;
    const problem = problemOf(err);
    if (problem.status === 0) {
      this.status.set('offline');
      this.writeBuffer(event, fields);
      this.deps.onOffline();
    } else if (problem.status === 409 && problem.code === 'conflict') {
      this.conflicted(err);
    } else if (problem.status >= 500) {
      this.status.set('unsaved');
      this.deps.onError(err);
      this.schedule();
    } else {
      this.stopTimer();
      this.status.set('error');
      this.deps.onError(err);
    }
  }

  private conflicted(err: unknown): void {
    this.status.set('conflict');
    this.stopTimer();
    this.deps.onConflict((problemOf(err).current as EventDto | undefined) ?? null);
  }

  private schedule(): void {
    this.stopTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      this.flush();
    }, AUTOSAVE_MS);
  }

  private stopTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private restartIdle(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => this.applyIdle(), IDLE_APPLY_MS);
  }

  private applyIdle(): void {
    const event = this.deps.event();
    if (
      !event ||
      !this.dirty() ||
      !IDLE_STATES.includes(event.state) ||
      this.status() === 'conflict'
    )
      return;
    this.save().subscribe({
      next: (updated) => this.deps.onApplied(updated),
      error: (err: unknown) => this.deps.onError(err),
    });
  }

  private cleared(saved: boolean, forgetBuffer: boolean): void {
    this.stopTimer();
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = null;
    this.fields.set({});
    this.sent.set({});
    if (forgetBuffer) this.removeBuffer();
    this.status.set(saved ? 'saved' : 'idle');
    if (saved) this.savedAt.set(new Date());
  }

  private drop(): void {
    const event = this.deps.event();
    this.sent.set({});
    this.removeBuffer();
    if (event) this.deps.api.discardDraft(event.id).subscribe({ error: () => undefined });
  }

  private key(eventId: string): string | null {
    const sub = this.deps.sub();
    return sub ? `draft:${eventId}:${sub}` : null;
  }

  private store(): Storage | null {
    try {
      return this.deps.storage ? this.deps.storage() : localStorage;
    } catch {
      return null;
    }
  }

  private writeBuffer(event: EventDto, fields: EventFields): void {
    const key = this.key(event.id);
    if (!key) return;
    const entry: Buffered = { baseRev: event.rev, fields, at: new Date().toISOString() };
    try {
      this.store()?.setItem(key, JSON.stringify(entry));
    } catch {
      /* storage may be blocked; the draft then lives in memory only */
    }
  }

  private readBuffer(eventId: string): Buffered | null {
    const key = this.key(eventId);
    if (!key) return null;
    try {
      const raw = this.store()?.getItem(key);
      return raw ? (JSON.parse(raw) as Buffered) : null;
    } catch {
      return null;
    }
  }

  private removeBuffer(): void {
    const event = this.deps.event();
    const key = event && this.key(event.id);
    if (!key) return;
    try {
      this.store()?.removeItem(key);
    } catch {
      /* see writeBuffer */
    }
  }
}
