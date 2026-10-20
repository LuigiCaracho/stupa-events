import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { AuthService } from '@core/auth/auth.service';
import { of, throwError } from 'rxjs';
import type { NotificationOut } from '../dossiers/model/notification.models';
import { NotificationsApi } from './notifications-api.service';
import { COUNT_CAP, NotificationsStore, POLL_MS } from './notifications.store';

const item = (id: string, readAt: string | null = null): NotificationOut => ({
  id,
  kind: 'comment_added',
  eventId: 'e1',
  eventTitle: 'Movienight',
  params: {},
  link: '/dossiers/e1',
  createdAt: '2026-10-01T10:00:00Z',
  readAt,
});

const page = (items: NotificationOut[], nextCursor: string | null = null) => ({
  items,
  nextCursor,
});

function setup(api: Record<string, unknown> = {}, userId: string | null = 'me') {
  const fake = {
    unreadCount: jest.fn(() => of(3)),
    list: jest.fn(() => of(page([item('n1'), item('n2', '2026-10-02T10:00:00Z')]))),
    markRead: jest.fn(() => of(undefined)),
    markAllRead: jest.fn(() => of(undefined)),
    ...api,
  };
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: '**', children: [] }]),
      { provide: NotificationsApi, useValue: fake },
      { provide: AuthService, useValue: { userId: () => userId } },
    ],
  });
  return { store: TestBed.inject(NotificationsStore), api: fake };
}

describe('NotificationsStore', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it('asks for the counter every minute, on route changes, and caps the badge', async () => {
    const { store, api } = setup();
    jest.advanceTimersByTime(POLL_MS);
    expect(api.unreadCount).toHaveBeenCalledTimes(1);
    expect(store.count()).toBe(3);
    expect(store.badge()).toBe('3');
    await TestBed.inject(Router).navigateByUrl('/x');
    expect(api.unreadCount).toHaveBeenCalledTimes(2);
    store.count.set(COUNT_CAP + 5);
    expect(store.badge()).toBe('99+');
  });

  it('does not ask without a session or while the tab is hidden', () => {
    const { store, api } = setup({}, null);
    expect(store.signedIn()).toBe(false);
    store.refreshCount();
    expect(api.unreadCount).not.toHaveBeenCalled();
    TestBed.resetTestingModule();
    const second = setup();
    jest.spyOn(TestBed.inject(DOCUMENT), 'visibilityState', 'get').mockReturnValue('hidden');
    second.store.refreshCount();
    expect(second.api.unreadCount).not.toHaveBeenCalled();
  });

  it('keeps the last number when the counter call fails', () => {
    const { store } = setup({ unreadCount: jest.fn(() => throwError(() => new Error('x'))) });
    store.count.set(2);
    store.refreshCount();
    expect(store.count()).toBe(2);
  });

  it('loads the list when the inbox opens and refreshes the counter', () => {
    const { store, api } = setup();
    store.openInbox();
    expect(store.open()).toBe(true);
    expect(store.items()).toHaveLength(2);
    expect(store.loading()).toBe(false);
    expect(api.unreadCount).toHaveBeenCalled();
  });

  it('loads older entries with the cursor and drops duplicates', () => {
    const list = jest
      .fn()
      .mockReturnValueOnce(of(page([item('n1'), item('n2')], 'c1')))
      .mockReturnValueOnce(of(page([item('n2'), item('n3')])));
    const { store } = setup({ list });
    store.load();
    expect(store.nextCursor()).toBe('c1');
    store.loadMore();
    expect(list).toHaveBeenLastCalledWith(false, 30, 'c1');
    expect(store.items().map((i) => i.id)).toEqual(['n1', 'n2', 'n3']);
    expect(store.nextCursor()).toBeNull();
    store.loadMore();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('flags a failed list', () => {
    const { store } = setup({ list: jest.fn(() => throwError(() => new Error('x'))) });
    store.load();
    expect(store.failed()).toBe(true);
    expect(store.loading()).toBe(false);
  });

  it('marks one entry read at once and the counter down, never below zero', () => {
    const { store, api } = setup();
    store.load();
    store.count.set(1);
    store.markRead(store.items()[0]);
    expect(store.items()[0].readAt).not.toBeNull();
    expect(store.count()).toBe(0);
    expect(api.markRead).toHaveBeenCalledWith('n1');
    store.markRead(store.items()[0]);
    expect(api.markRead).toHaveBeenCalledTimes(1);
    store.markRead(item('n3'));
    expect(store.count()).toBe(0);
  });

  it('marks everything read and falls back to the server count on errors', () => {
    const { store, api } = setup({
      markAllRead: jest.fn(() => throwError(() => new Error('x'))),
      markRead: jest.fn(() => throwError(() => new Error('x'))),
    });
    store.load();
    store.markAllRead();
    expect(store.items().every((i) => !!i.readAt)).toBe(true);
    expect(api.unreadCount).toHaveBeenCalled();
    store.items.set([item('n9')]);
    store.markRead(store.items()[0]);
    expect(api.unreadCount.mock.calls.length).toBeGreaterThan(1);
  });
});
