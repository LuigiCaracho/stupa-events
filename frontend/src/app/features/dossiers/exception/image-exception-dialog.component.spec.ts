import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { EventsApi } from '../api/events-api.service';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { ImageExceptionDialogComponent } from './image-exception-dialog.component';

describe('ImageExceptionDialogComponent', () => {
  async function setup(api = fakeApi()) {
    const granted = jest.fn();
    const toast = { success: jest.fn(), error: jest.fn() };
    await render(ImageExceptionDialogComponent, {
      inputs: { event: makeEvent() },
      providers: [
        { provide: EventsApi, useValue: api },
        { provide: ToastService, useValue: toast },
      ],
      on: { granted },
    });
    return { api, granted, toast };
  }

  it('refuses a reason shorter than ten characters', async () => {
    const { api } = await setup();
    await userEvent.type(screen.getByLabelText(/Begründung/), 'kurz');
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme erteilen' }));
    expect(api.action).not.toHaveBeenCalled();
    expect(screen.getByText('Begründung zu kurz (mindestens 10 Zeichen).')).toBeInTheDocument();
  });

  it('grants the exception with the trimmed reason', async () => {
    const { api, granted } = await setup();
    await userEvent.type(screen.getByLabelText(/Begründung/), '  Offenes Präsidium ohne Plakat ');
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme erteilen' }));
    expect(api.action).toHaveBeenCalledWith(
      'ev-1',
      'image-exception',
      { reason: 'Offenes Präsidium ohne Plakat' },
      3,
    );
    expect(granted).toHaveBeenCalled();
  });

  it('keeps the dialog open when the server refuses', async () => {
    const forbidden = new HttpErrorResponse({
      status: 403,
      error: { status: 403, code: 'forbidden' },
    });
    const { granted } = await setup(
      fakeApi({ action: jest.fn(() => throwError(() => forbidden)) }),
    );
    await userEvent.type(screen.getByLabelText(/Begründung/), 'Offenes Präsidium ohne Plakat');
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme erteilen' }));
    expect(granted).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('names a locked dossier on 409', async () => {
    const locked = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'field_locked' },
    });
    const { granted, toast } = await setup(
      fakeApi({ action: jest.fn(() => throwError(() => locked)) }),
    );
    await userEvent.type(screen.getByLabelText(/Begründung/), 'Offenes Präsidium ohne Plakat');
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme erteilen' }));
    expect(granted).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      'In diesem Zustand lässt sich keine Ausnahme mehr erteilen.',
    );
  });

  it('shows the generic text for another failure', async () => {
    const { toast } = await setup(
      fakeApi({ action: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    await userEvent.type(screen.getByLabelText(/Begründung/), 'Offenes Präsidium ohne Plakat');
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme erteilen' }));
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('Das hat nicht geklappt'));
  });

  it('tells that the exception only counts for this event', async () => {
    await setup();
    expect(
      screen.getByText(/nur für dieses Event, nicht für Kopien und Serientermine/),
    ).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
  });
});
