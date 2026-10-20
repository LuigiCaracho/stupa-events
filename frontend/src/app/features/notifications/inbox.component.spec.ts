import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { Router, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '@core/auth/auth.service';
import { of } from 'rxjs';
import { runAxe } from '../../../testing/a11y';
import type { NotificationOut } from '../dossiers/model/notification.models';
import { InboxComponent } from './inbox.component';
import { NotificationsApi } from './notifications-api.service';
import { NotificationsStore } from './notifications.store';

const item = (id: string, o: Partial<NotificationOut> = {}): NotificationOut => ({
  id,
  kind: 'changes_requested',
  eventId: 'e1',
  eventTitle: 'Movienight',
  params: {},
  link: '/dossiers/e1',
  createdAt: '2026-10-01T10:00:00Z',
  readAt: null,
  ...o,
});

async function setup(items: NotificationOut[], more = false, older: NotificationOut[] = []) {
  const api = {
    list: jest.fn((_u?: boolean, _l?: number, cursor?: string | null) =>
      of(cursor ? { items: older, nextCursor: null } : { items, nextCursor: more ? 'c1' : null }),
    ),
    unreadCount: jest.fn(() => of(items.filter((i) => !i.readAt).length)),
    markRead: jest.fn(() => of(undefined)),
    markAllRead: jest.fn(() => of(undefined)),
  };
  const view = await render(InboxComponent, {
    providers: [
      provideRouter([{ path: '**', children: [] }]),
      { provide: NotificationsApi, useValue: api },
      { provide: AuthService, useValue: { userId: () => 'me' } },
    ],
  });
  const store = TestBed.inject(NotificationsStore);
  store.openInbox();
  view.fixture.detectChanges();
  return { ...view, api, store };
}

describe('InboxComponent', () => {
  it('lists entries with the kind as text and unread ones with a hidden word and a dot', async () => {
    const { container } = await setup([
      item('n1'),
      item('n2', { kind: 'transition_done', eventTitle: null, readAt: '2026-10-02T10:00:00Z' }),
    ]);
    expect(await screen.findByText('Änderungen erbeten')).toBeInTheDocument();
    expect(screen.getByText('Ungelesen:')).toBeInTheDocument();
    expect(screen.getAllByText('Ungelesen:')).toHaveLength(1);
    expect(screen.getByText('Statuswechsel')).toBeInTheDocument();
    expect(await runAxe(document.body)).toHaveNoViolations();
    expect(container).toBeTruthy();
  });

  it('marks read and goes to the link on a click', async () => {
    const { api, store } = await setup([item('n1')]);
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    await userEvent.click(await screen.findByRole('button', { name: /Änderungen erbeten/ }));
    expect(api.markRead).toHaveBeenCalledWith('n1');
    expect(navigate).toHaveBeenCalledWith('/dossiers/e1');
    expect(store.open()).toBe(false);
  });

  it('stays put for an entry without a link', async () => {
    await setup([item('n1', { link: '' })]);
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigateByUrl');
    await userEvent.click(await screen.findByRole('button', { name: /Änderungen erbeten/ }));
    expect(navigate).not.toHaveBeenCalled();
  });

  it('marks everything read', async () => {
    const { api } = await setup([item('n1'), item('n2')]);
    await userEvent.click(await screen.findByRole('button', { name: 'Alle gelesen' }));
    expect(api.markAllRead).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Alle gelesen' })).toBeDisabled();
  });

  it('offers older entries when the server has more and appends them', async () => {
    const { api } = await setup([item('n1')], true, [item('n2', { kind: 'transition_done' })]);
    await userEvent.click(await screen.findByRole('button', { name: 'Ältere laden' }));
    expect(api.list).toHaveBeenLastCalledWith(false, 30, 'c1');
    expect(await screen.findByText('Statuswechsel')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ältere laden' })).toBeNull();
  });

  it('says so when it is empty', async () => {
    await setup([]);
    expect(await screen.findByText('Keine neuen Benachrichtigungen.')).toBeInTheDocument();
  });

  it('shows an error note when loading fails', async () => {
    const { store, fixture } = await setup([]);
    store.failed.set(true);
    fixture.detectChanges();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Benachrichtigungen konnten nicht geladen werden.',
    );
  });
});
