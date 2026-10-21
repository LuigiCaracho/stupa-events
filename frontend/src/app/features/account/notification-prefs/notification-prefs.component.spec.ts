import { HttpErrorResponse } from '@angular/common/http';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { defer, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { NotificationsApi } from '../../notifications/notifications-api.service';
import { NotificationPrefsComponent } from './notification-prefs.component';

const prefs = [
  { kind: 'published', inApp: true, mail: true, mailAvailable: true, essential: true },
  { kind: 'comment_added', inApp: true, mail: false, mailAvailable: true, essential: false },
];

async function setup(api: Record<string, unknown> = {}) {
  const fake = { prefs: jest.fn(() => of(prefs)), savePrefs: jest.fn(() => of(prefs)), ...api };
  const view = await render(NotificationPrefsComponent, {
    providers: [{ provide: NotificationsApi, useValue: fake }],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api: fake, error: jest.spyOn(toast, 'error') };
}

describe('NotificationPrefsComponent', () => {
  it('shows two switches per kind and locks the essential one with a note', async () => {
    const { container } = await setup();
    expect(screen.getByText('Veröffentlicht')).toBeInTheDocument();
    expect(screen.getByText('Immer aktiv')).toBeInTheDocument();
    const switches = screen.getAllByRole('switch');
    expect(switches).toHaveLength(4);
    expect(switches[0]).toBeDisabled();
    expect(switches[1]).toBeDisabled();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('shows no mail switch for a kind that never sends mail', async () => {
    await setup({
      prefs: jest.fn(() =>
        of([
          {
            kind: 'cancelled',
            inApp: true,
            mail: false,
            mailAvailable: false,
            essential: false,
          },
        ]),
      ),
    });
    expect(await screen.findAllByRole('switch')).toHaveLength(1);
    expect(screen.queryByText('Per Mail')).toBeNull();
  });

  it('saves a switch at once', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getAllByRole('switch')[3]);
    expect(api.savePrefs).toHaveBeenCalledWith([
      { kind: 'comment_added', inApp: true, mail: true },
    ]);
    expect(screen.getAllByRole('switch')[3]).toBeChecked();
  });

  it('falls back and reports when saving fails', async () => {
    const refusal = new HttpErrorResponse({
      status: 422,
      error: { status: 422, code: 'kind_essential' },
    });
    const { error } = await setup({
      savePrefs: jest.fn(() => defer(() => Promise.reject(refusal))),
    });
    await userEvent.click(screen.getAllByRole('switch')[2]);
    await waitFor(() =>
      expect(error).toHaveBeenCalledWith('Diese Benachrichtigung ist immer aktiv.'),
    );
    await waitFor(() => expect(screen.getAllByRole('switch')[2]).toBeChecked());
  });

  it('shows an error note when the list fails', async () => {
    await setup({ prefs: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Einstellungen konnten nicht geladen werden.',
    );
  });
});
