import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { OutcomeApi } from '../api/outcome-api.service';
import { OutcomeFormComponent } from './outcome-form.component';

async function setup(putOutcome = jest.fn(() => of(makeEvent({ rev: 4 }))), inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const view = await render(OutcomeFormComponent, {
    inputs: { event: makeEvent({ state: 'archived' }), canEdit: true, ...inputs },
    providers: [{ provide: OutcomeApi, useValue: { putOutcome } }],
    on: { changed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, putOutcome, changed, toasts: () => TestBed.inject(ToastService).toasts().map((t) => t.message) };
}

describe('OutcomeFormComponent', () => {
  it('saves attendance and costs with the revision and reports the new dossier', async () => {
    const { putOutcome, changed, toasts } = await setup();
    await userEvent.type(screen.getByLabelText('Besucher:innen'), '87');
    await userEvent.type(screen.getByLabelText(/Kosten \(Ist\)/), '245');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(putOutcome).toHaveBeenCalledWith('ev-1', 3, {
      attendance: 87,
      costsCents: 24500,
      revenueCents: null,
      notes: null,
      waived: false,
      waivedReason: null,
    });
    expect(changed).toHaveBeenCalledWith(expect.objectContaining({ rev: 4 }));
    expect(toasts()).toContain('Ergebnis gespeichert.');
  });

  it('keeps 0 as a valid cost', async () => {
    const { putOutcome } = await setup();
    await userEvent.type(screen.getByLabelText('Besucher:innen'), '0');
    await userEvent.type(screen.getByLabelText(/Kosten \(Ist\)/), '0');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(putOutcome).toHaveBeenCalledWith('ev-1', 3, expect.objectContaining({ attendance: 0, costsCents: 0 }));
  });

  it('shows the stored outcome', async () => {
    await setup(undefined, {
      event: makeEvent({
        state: 'archived',
        outcome: { attendance: 87, costsCents: 24500, revenueCents: 13000, notes: 'Gut', waived: false, waivedReason: null },
      }),
    });
    expect(screen.getByLabelText('Besucher:innen')).toHaveValue(87);
    expect(screen.getByLabelText('Notiz')).toHaveValue('Gut');
  });

  it('refuses a fraction of a person without a request', async () => {
    const { putOutcome } = await setup();
    await userEvent.type(screen.getByLabelText('Besucher:innen'), '2.5');
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(await screen.findByText('Bitte eine ganze Zahl ab 0 eintragen.')).toBeInTheDocument();
    expect(putOutcome).not.toHaveBeenCalled();
  });

  it('waives without a reason and clears the numbers', async () => {
    const { putOutcome } = await setup();
    await userEvent.click(screen.getByRole('switch', { name: 'Verzichtet' }));
    expect(screen.queryByLabelText('Besucher:innen')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(putOutcome).toHaveBeenCalledWith('ev-1', 3, {
      attendance: null,
      costsCents: null,
      revenueCents: null,
      notes: null,
      waived: true,
      waivedReason: null,
    });
  });

  it('sends a reason along when there is one', async () => {
    const { putOutcome } = await setup();
    await userEvent.click(screen.getByRole('switch', { name: 'Verzichtet' }));
    await userEvent.type(screen.getByLabelText(/Grund/), 'kein Eintritt');
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(putOutcome).toHaveBeenCalledWith(
      'ev-1',
      3,
      expect.objectContaining({ waived: true, waivedReason: 'kein Eintritt' }),
    );
  });

  it('asks for a reload when somebody else changed the dossier', async () => {
    await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } }))),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Jemand anderes hat das Dossier geändert/);
  });

  it('shows the message of any other refusal', async () => {
    const { toasts } = await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    await screen.findByText('Ergebnis');
    expect(toasts().length).toBe(1);
  });

  it('shows the stored result as text without the right to edit', async () => {
    await setup(undefined, {
      canEdit: false,
      event: makeEvent({
        state: 'archived',
        outcome: { attendance: 87, costsCents: 24500, revenueCents: null, notes: 'Gut', waived: false, waivedReason: null },
      }),
    });
    expect(screen.queryByRole('button', { name: 'Ergebnis speichern' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Besucher:innen')).not.toBeInTheDocument();
    expect(screen.getByText('87')).toBeInTheDocument();
    expect(screen.getByText(/245,00/)).toBeInTheDocument();
    expect(screen.getByText('–')).toBeInTheDocument();
    expect(screen.getByText('Gut')).toBeInTheDocument();
  });

  it('shows the waiver and its reason, or that nothing was entered', async () => {
    const view = await setup(undefined, {
      canEdit: false,
      event: makeEvent({
        state: 'archived',
        outcome: { attendance: null, costsCents: null, revenueCents: null, notes: null, waived: true, waivedReason: 'Kein Eintritt' },
      }),
    });
    expect(screen.getByText('Verzichtet: Kein Eintritt')).toBeInTheDocument();
    view.view.fixture.componentRef.setInput('event', makeEvent({ state: 'archived', outcome: null }));
    view.view.fixture.detectChanges();
    expect(screen.getByText('Noch kein Ergebnis eingetragen.')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('keeps what is typed when the dossier reloads without a new result', async () => {
    const { view } = await setup();
    await userEvent.type(screen.getByLabelText('Besucher:innen'), '42');
    view.fixture.componentRef.setInput('event', makeEvent({ state: 'archived', rev: 4, title: 'Anders' }));
    view.fixture.detectChanges();
    expect(screen.getByLabelText('Besucher:innen')).toHaveValue(42);
  });
});
