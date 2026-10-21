import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { EventsApi } from '../api/events-api.service';
import type { CancelMode } from './cancel-request';
import { CancelDialogComponent } from './cancel-dialog.component';

async function setup(api = fakeApi(), mode: CancelMode = 'cancel') {
  const done = jest.fn();
  const stale = jest.fn();
  const closed = jest.fn();
  const view = await render(CancelDialogComponent, {
    inputs: { event: makeEvent({ state: 'published', rev: 6 }), mode },
    providers: [{ provide: EventsApi, useValue: api }],
    on: { done, stale, closed },
  });
  return {
    view,
    api,
    done,
    stale,
    closed,
    toasts: () =>
      TestBed.inject(ToastService)
        .toasts()
        .map((t) => t.message),
  };
}

const submit = (name: string) =>
  screen.getAllByRole('button', { name }).at(-1)!;

describe('CancelDialogComponent', () => {
  it('cancels without any text: the internal note is optional', async () => {
    const { api, done } = await setup();
    await userEvent.click(submit('Absagen'));
    expect(api.cancel).toHaveBeenCalledWith('ev-1', 6, { publicReasonCode: 'none' });
    expect(done).toHaveBeenCalled();
  });

  it('cancels with the note, the public reason and the public text', async () => {
    const { api } = await setup();
    await userEvent.type(screen.getByLabelText(/Notiz \(intern/), 'Referent krank');
    await userEvent.click(screen.getByRole('combobox', { name: /Öffentlicher Grund/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Krankheit' }));
    await userEvent.type(screen.getByLabelText('Öffentlicher Kurztext'), 'Wir holen es nach');
    expect(screen.getByText('So erscheint es öffentlich: Abgesagt · Krankheit')).toBeInTheDocument();
    await userEvent.click(submit('Absagen'));
    expect(api.cancel).toHaveBeenCalledWith('ev-1', 6, {
      reason: 'Referent krank',
      publicReasonCode: 'illness',
      publicReasonText: 'Wir holen es nach',
    });
  });

  it('postpones with a new date', async () => {
    const { api } = await setup(fakeApi(), 'postpone');
    expect(screen.getByText(/Abonnent:innen sehen die Absage/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Datum/), '01.12.2099');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Uhrzeit/), '19:00');
    await userEvent.tab();
    await userEvent.click(submit('Verschieben'));
    expect(api.postpone).toHaveBeenCalledWith('ev-1', 6, {
      publicReasonCode: 'none',
      newStartsAt: '2099-12-01T18:00:00Z',
    });
  });

  it('postpones without a date: the new date follows', async () => {
    const { api } = await setup(fakeApi(), 'postpone');
    await userEvent.click(submit('Verschieben'));
    expect(api.postpone).toHaveBeenCalledWith('ev-1', 6, { publicReasonCode: 'none' });
  });

  it('refuses a new date in the past', async () => {
    const { api } = await setup(fakeApi(), 'postpone');
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Datum/), '01.01.2020');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Uhrzeit/), '19:00');
    await userEvent.tab();
    await userEvent.click(submit('Verschieben'));
    expect(screen.getByText('Neues Datum muss in der Zukunft liegen.')).toBeInTheDocument();
    expect(api.postpone).not.toHaveBeenCalled();
  });

  it('puts the event back on with an optional note and no public fields', async () => {
    const { api, done } = await setup(fakeApi(), 'reinstate');
    expect(screen.queryByLabelText('Öffentlicher Kurztext')).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Notiz \(intern/), 'Raum ist frei');
    await userEvent.click(submit('Wieder ansetzen'));
    expect(api.reinstate).toHaveBeenCalledWith('ev-1', 6, { reason: 'Raum ist frei' });
    expect(done).toHaveBeenCalled();
  });

  it('reports a stale dossier and other refusals', async () => {
    const stale409 = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'invalid_state' },
    });
    const bad = new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } });
    const api = fakeApi({
      cancel: jest
        .fn()
        .mockReturnValueOnce(throwError(() => stale409))
        .mockReturnValueOnce(throwError(() => bad)),
    });
    const { stale, toasts, done } = await setup(api);
    await userEvent.click(submit('Absagen'));
    expect(stale).toHaveBeenCalled();
    await userEvent.click(submit('Absagen'));
    expect(toasts()[1]).toBe('Dafür fehlt dir die Berechtigung.');
    expect(done).not.toHaveBeenCalled();
  });

  it('closes and has no axe violations', async () => {
    const { closed } = await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });
});
