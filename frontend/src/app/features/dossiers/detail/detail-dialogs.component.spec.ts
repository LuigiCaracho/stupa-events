import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { throwError } from 'rxjs';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { EventsApi } from '../api/events-api.service';
import { DetailDialogsComponent, type DialogState } from './detail-dialogs.component';

async function setup(state: DialogState, api = fakeApi()) {
  const outputs = {
    applied: jest.fn(),
    stale: jest.fn(),
    closed: jest.fn(),
    leave: jest.fn(),
    keep: jest.fn(),
    theirs: jest.fn(),
  };
  await render(DetailDialogsComponent, {
    inputs: { event: makeEvent({ state: 'live', rev: 6 }), state },
    providers: [{ provide: EventsApi, useValue: api }],
    on: outputs,
  });
  return {
    api,
    ...outputs,
    toasts: () =>
      TestBed.inject(ToastService)
        .toasts()
        .map((t) => t.message),
  };
}

describe('DetailDialogsComponent', () => {
  it('renders no dialog without a state', async () => {
    await setup(null);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('reinstates with the reason and reports a stale dossier', async () => {
    const stale409 = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'conflict' },
    });
    const { api, stale, toasts, applied } = await setup(
      { kind: 'reinstate' },
      fakeApi({ action: jest.fn(() => throwError(() => stale409)) }),
    );
    await userEvent.type(
      screen.getByLabelText(/Warum nimmst du die Absage zurück/),
      'Termin steht',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(api.action).toHaveBeenCalledWith('ev-1', 'reinstate', { reason: 'Termin steht' }, 6);
    expect(stale).toHaveBeenCalled();
    expect(toasts()[0]).toContain('Jemand anderes');
    expect(applied).not.toHaveBeenCalled();
  });

  it('reverts with the note and shows another failure without a reload', async () => {
    const down = new HttpErrorResponse({ status: 500 });
    const { api, stale, toasts } = await setup(
      { kind: 'revert', rev: 2 },
      fakeApi({ action: jest.fn(() => throwError(() => down)) }),
    );
    await userEvent.type(screen.getByLabelText('Notiz (optional)'), 'zurück');
    await userEvent.click(screen.getByRole('button', { name: 'Auf diesen Stand zurücksetzen' }));
    expect(api.action).toHaveBeenCalledWith(
      'ev-1',
      'revert-revision',
      { rev: 2, note: 'zurück' },
      6,
    );
    expect(toasts()[0]).toContain('Das hat nicht geklappt');
    expect(stale).not.toHaveBeenCalled();
  });

  it('applies the result of a revert without a note', async () => {
    const { api, applied } = await setup({ kind: 'revert', rev: 2 });
    await userEvent.click(screen.getByRole('button', { name: 'Auf diesen Stand zurücksetzen' }));
    expect(api.action).toHaveBeenCalledWith('ev-1', 'revert-revision', { rev: 2 }, 6);
    expect(applied).toHaveBeenCalled();
  });

  it('answers the question on leaving through its three buttons and the close cross', async () => {
    const { leave } = await setup({ kind: 'leave', resolve: jest.fn() });
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Bleiben' }));
    await userEvent.click(screen.getByRole('button', { name: 'Schließen' }));
    expect(leave.mock.calls.map(([c]) => c)).toEqual(['save', 'discard', 'stay', 'stay']);
  });
});
