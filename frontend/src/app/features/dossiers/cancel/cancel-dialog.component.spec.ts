import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { EventsApi } from '../api/events-api.service';
import { CancelDialogComponent } from './cancel-dialog.component';

const ALL = ['cancel', 'postpone', 'postpone-with-date', 'public-text'];

async function setup(api = fakeApi(), allowedActions: string[] = ALL) {
  const done = jest.fn();
  const stale = jest.fn();
  const closed = jest.fn();
  const view = await render(CancelDialogComponent, {
    inputs: { event: makeEvent({ state: 'live', rev: 6, allowedActions }) },
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

describe('CancelDialogComponent', () => {
  it('needs the internal reason before it cancels', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Absagen', hidden: false }));
    expect(screen.getByText('Grund fehlt.')).toBeInTheDocument();
    expect(api.action).not.toHaveBeenCalled();
  });

  it('cancels with the reason, the public reason and the public text', async () => {
    const { api, done } = await setup();
    await userEvent.type(screen.getByLabelText(/Grund \(intern\)/), 'Referent krank');
    await userEvent.click(screen.getByRole('combobox', { name: /Öffentlicher Grund/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Krankheit' }));
    await userEvent.type(screen.getByLabelText('Öffentlicher Kurztext'), 'Wir holen es nach');
    expect(
      screen.getByText('So erscheint es öffentlich: Abgesagt · Krankheit'),
    ).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Absagen' }).at(-1)!);
    expect(api.action).toHaveBeenCalledWith(
      'ev-1',
      'cancel',
      {
        reason: 'Referent krank',
        publicReasonCode: 'illness',
        publicReasonText: 'Wir holen es nach',
      },
      6,
    );
    expect(done).toHaveBeenCalled();
  });

  it('postpones with a new date when the person may change critical fields', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: /Verschieben/ }));
    expect(screen.getByText(/Abonnent:innen sehen die Absage/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^Grund \(intern\)/), 'Raum belegt');
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Datum/), '01.12.2099');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Uhrzeit/), '19:00');
    await userEvent.tab();
    await userEvent.click(screen.getAllByRole('button', { name: 'Verschieben' }).at(-1)!);
    expect(api.action).toHaveBeenCalledWith(
      'ev-1',
      'postpone',
      {
        reason: 'Raum belegt',
        publicReasonCode: 'none',
        newStartsAt: '2099-12-01T18:00:00Z',
        publicReasonText: undefined,
      },
      6,
    );
  });

  it('refuses a new date in the past', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: /Verschieben/ }));
    await userEvent.type(screen.getByLabelText(/^Grund \(intern\)/), 'x');
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Datum/), '01.01.2020');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Neuer Termin, Uhrzeit/), '19:00');
    await userEvent.tab();
    await userEvent.click(screen.getAllByRole('button', { name: 'Verschieben' }).at(-1)!);
    expect(screen.getByText('Neues Datum muss in der Zukunft liegen.')).toBeInTheDocument();
    expect(api.action).not.toHaveBeenCalled();
  });

  it('offers neither the public text nor a new date without the rights', async () => {
    await setup(fakeApi(), ['cancel', 'postpone']);
    expect(screen.queryByLabelText('Öffentlicher Kurztext')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: /Verschieben/ }));
    expect(screen.getByText(/Neuer Termin folgt/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Neuer Termin, Datum/)).not.toBeInTheDocument();
  });

  it('reports a stale dossier and other refusals', async () => {
    const stale409 = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'conflict' },
    });
    const bad = new HttpErrorResponse({
      status: 422,
      error: { status: 422, code: 'reason_required' },
    });
    const api = fakeApi({
      action: jest
        .fn()
        .mockReturnValueOnce(throwError(() => stale409))
        .mockReturnValueOnce(throwError(() => bad)),
    });
    const { stale, toasts, done } = await setup(api);
    await userEvent.type(screen.getByLabelText(/^Grund \(intern\)/), 'x');
    await userEvent.click(screen.getAllByRole('button', { name: 'Absagen' }).at(-1)!);
    expect(stale).toHaveBeenCalled();
    await userEvent.click(screen.getAllByRole('button', { name: 'Absagen' }).at(-1)!);
    expect(toasts()[1]).toBe('Bitte gib einen Grund an.');
    expect(done).not.toHaveBeenCalled();
  });

  it('closes and has no axe violations', async () => {
    const { closed } = await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });
});
