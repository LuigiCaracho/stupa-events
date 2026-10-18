import { HttpErrorResponse } from '@angular/common/http';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { EventsApi } from '../api/events-api.service';
import { fakeApi, makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import { runAxe } from '../../../../testing/a11y';
import { TransitionDialogComponent } from './transition-dialog.component';

const blocker = {
  code: 'image_required',
  field: null,
  severity: 'blocker' as const,
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster' as const,
};
const warning = { ...blocker, code: 'start_in_past', severity: 'warning' as const, messageKey: 'guards.start_in_past', fixAction: null };

describe('TransitionDialogComponent', () => {
  async function setup(api = fakeApi(), transition: 'T02' | 'T04' = 'T02') {
    const done = jest.fn();
    const stale = jest.fn();
    const fix = jest.fn();
    const closed = jest.fn();
    const view = await render(TransitionDialogComponent, {
      inputs: { event: makeEvent({ state: 'in_review' }), transition },
      providers: [{ provide: EventsApi, useValue: api }],
      on: { done, stale, fix, closed },
    });
    return { view, api, done, stale, fix, closed };
  }

  it('titles the dialog with the transition and confirms when nothing blocks', async () => {
    const { api, done } = await setup();
    expect(await screen.findByRole('dialog', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    expect(api.guards).toHaveBeenCalledWith('ev-1', 'T02');
    await userEvent.type(screen.getByLabelText(/Notiz/), ' bitte prüfen ');
    await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
    expect(api.transition).toHaveBeenCalledWith('ev-1', 'T02', 'bitte prüfen');
    expect(done).toHaveBeenCalled();
  });

  it('keeps the confirm button off with a visible reason while a blocker is open', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [blocker] }))) });
    const { fix } = await setup(api, 'T04');
    expect(await screen.findByText('Poster fehlt oder ist nicht freigegeben.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Noch nicht möglich');
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(fix).toHaveBeenCalledWith(blocker);
  });

  it('needs the tick for a warning', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ reasons: [warning] }))) });
    await setup(api);
    const confirm = await screen.findByRole('button', { name: 'Bestätigen' });
    expect(confirm).toBeDisabled();
    await userEvent.click(await screen.findByLabelText('Ich habe die Hinweise gelesen.'));
    expect(confirm).toBeEnabled();
  });

  it('reports a stale revision and a refused transition', async () => {
    const conflict = new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } });
    const refused = new HttpErrorResponse({ status: 422, error: { status: 422, code: 'image_required', reasons: [blocker] } });
    const api = fakeApi({ transition: jest.fn().mockReturnValueOnce(throwError(() => conflict)).mockReturnValueOnce(throwError(() => refused)) });
    const { stale } = await setup(api);
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    expect(stale).toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
    expect(api.guards).toHaveBeenCalledTimes(2);
  });

  it('keeps the confirm button off when the role may not fire the transition', async () => {
    const forbidden = { ...blocker, code: 'forbidden', messageKey: 'guards.forbidden', fixAction: null };
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [forbidden] }))) });
    await setup(api, 'T04');
    expect(await screen.findByText('Dafür fehlt dir die Berechtigung.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  });

  it('keeps the confirm button off when the server says not allowed without a reason', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [] }))) });
    await setup(api, 'T04');
    expect(await screen.findByText(/Noch nicht möglich/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  });

  it('tells the cause when the guards cannot be read and retries on request', async () => {
    const offline = new HttpErrorResponse({ status: 0 });
    const api = fakeApi({ guards: jest.fn().mockReturnValueOnce(throwError(() => offline)).mockReturnValue(of(makeGuards())) });
    await setup(api);
    expect(await screen.findByRole('alert')).toHaveTextContent('Keine Verbindung');
    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeEnabled());
    expect(api.guards).toHaveBeenCalledTimes(2);
  });

  it('closes from the cancel button and has no axe violations', async () => {
    const { closed, view } = await setup();
    await screen.findByRole('button', { name: 'Bestätigen' });
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
    view.fixture.destroy();
  });
});
