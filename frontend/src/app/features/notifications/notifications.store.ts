/**
 * State of the bell (I28, contract 5.7): the unread counter and the list of the inbox. The counter is asked every 60 s
 * while the tab is visible and on every route change; there is no server push. All calls fail quiet (the bell keeps its
 * last number); the inbox shows its own error text.
 */
import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, NgZone, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { filter } from 'rxjs';
import type { NotificationOut } from '../dossiers/model/notification.models';
import { NotificationsApi } from './notifications-api.service';

export const POLL_MS = 60_000;
export const COUNT_CAP = 99;

@Injectable({ providedIn: 'root' })
export class NotificationsStore {
  private readonly api = inject(NotificationsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly doc = inject(DOCUMENT);
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly signedIn = computed(() => !!this.auth.userId());
  readonly count = signal(0);
  readonly items = signal<NotificationOut[]>([]);
  readonly open = signal(false);
  readonly loading = signal(false);
  readonly failed = signal(false);
  readonly nextCursor = signal<string | null>(null);
  readonly loadingMore = signal(false);

  readonly badge = computed(() =>
    this.count() > COUNT_CAP ? `${COUNT_CAP}+` : String(this.count()),
  );

  constructor() {
    const destroyRef = inject(DestroyRef);
    this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => this.refreshCount());
    this.timer = inject(NgZone).runOutsideAngular(() =>
      setInterval(() => this.refreshCount(), POLL_MS),
    );
    destroyRef.onDestroy(() => {
      if (this.timer) clearInterval(this.timer);
    });
  }

  refreshCount(): void {
    if (!this.auth.userId() || this.doc.visibilityState === 'hidden') return;
    this.api.unreadCount().subscribe({
      next: (n) => this.count.set(n),
      error: () => undefined,
    });
  }

  openInbox(): void {
    this.open.set(true);
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.failed.set(false);
    this.api.list().subscribe({
      next: (page) => {
        this.items.set(page.items);
        this.nextCursor.set(page.nextCursor);
        this.loading.set(false);
        this.refreshCount();
      },
      error: () => {
        this.loading.set(false);
        this.failed.set(true);
      },
    });
  }

  loadMore(): void {
    const cursor = this.nextCursor();
    if (!cursor || this.loadingMore()) return;
    this.loadingMore.set(true);
    this.api.list(false, 30, cursor).subscribe({
      next: (page) => {
        const known = new Set(this.items().map((i) => i.id));
        this.items.update((list) => [...list, ...page.items.filter((i) => !known.has(i.id))]);
        this.nextCursor.set(page.nextCursor);
        this.loadingMore.set(false);
      },
      error: () => {
        this.loadingMore.set(false);
        this.failed.set(true);
      },
    });
  }

  markRead(item: NotificationOut): void {
    if (item.readAt) return;
    this.items.update((list) =>
      list.map((i) => (i.id === item.id ? { ...i, readAt: new Date().toISOString() } : i)),
    );
    this.count.update((n) => Math.max(0, n - 1));
    this.api.markRead(item.id).subscribe({ error: () => this.refreshCount() });
  }

  markAllRead(): void {
    const now = new Date().toISOString();
    this.items.update((list) => list.map((i) => ({ ...i, readAt: i.readAt ?? now })));
    this.count.set(0);
    this.api.markAllRead().subscribe({ error: () => this.refreshCount() });
  }
}
