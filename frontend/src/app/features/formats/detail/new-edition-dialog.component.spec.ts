import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { FormatsApi } from '../api/formats-api.service';
import { NewEditionDialogComponent } from './new-edition-dialog.component';

async function setup(newEdition = jest.fn(() => of({ event: makeEvent({ id: 'new-1' }), report: [] }))) {
  const created = jest.fn();
  const closed = jest.fn();
  const view = await render(NewEditionDialogComponent, {
    inputs: { format: makeFormat() },
    providers: [
      { provide: FormatsApi, useValue: { newEdition } },
      { provide: EventsApi, useValue: fakeApi() },
      { provide: AuthService, useValue: fakeAuth() },
    ],
    on: { created, closed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, newEdition, created, closed };
}

async function fillDate() {
  await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2026');
  await userEvent.tab();
  await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:30');
  await userEvent.tab();
}

describe('NewEditionDialogComponent', () => {
  it('names the format and refuses without a date', async () => {
    const { newEdition } = await setup();
    expect(screen.getByRole('dialog', { name: 'Neue Ausgabe: Movienight' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(screen.getByText('Neues Datum fehlt.')).toBeInTheDocument();
    expect(newEdition).not.toHaveBeenCalled();
  });

  it('plans the edition with a UTC instant and reports the new dossier', async () => {
    const { newEdition, created } = await setup();
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(newEdition).toHaveBeenCalledWith('movienight', { startsAt: '2026-11-05T18:30:00Z' });
    expect(created).toHaveBeenCalledWith('new-1');
  });

  it('shows the message of a refusal', async () => {
    const { created } = await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    );
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(created).not.toHaveBeenCalled();
    expect(TestBed.inject(ToastService).toasts().length).toBe(1);
  });

  it('sends the chosen organization when there is a choice', async () => {
    const created = jest.fn();
    const newEdition = jest.fn(() => of({ event: makeEvent({ id: 'n2' }), report: [] }));
    await render(NewEditionDialogComponent, {
      inputs: { format: makeFormat() },
      providers: [
        { provide: FormatsApi, useValue: { newEdition } },
        {
          provide: EventsApi,
          useValue: fakeApi({
            organizations: jest.fn(() => of([
              { id: 'org-fsi', slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
              { id: 'org-mk', slug: 'makers', name: 'MAKERS', short: 'MKR' },
            ])),
          }),
        },
        { provide: AuthService, useValue: fakeAuth({ organizations: () => [{ slug: 'fsi', role: 'organizer' }, { slug: 'makers', role: 'organizer' }] }) },
      ],
      on: { created },
    });
    await userEvent.click(await screen.findByRole('combobox', { name: /Organisation/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'MAKERS' }));
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(newEdition).toHaveBeenCalledWith('movienight', { startsAt: '2026-11-05T18:30:00Z', organizationId: 'org-mk' });
    expect(created).toHaveBeenCalledWith('n2');
  });
});
