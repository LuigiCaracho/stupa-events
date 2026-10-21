import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { OutcomeApi } from '../api/outcome-api.service';
import { LocationDialogComponent } from './location-dialog.component';

async function setup(confirmLocation = jest.fn(() => of(makeEvent({ rev: 4, locationPrecision: 'building' })))) {
  const confirmed = jest.fn();
  const closed = jest.fn();
  const view = await render(LocationDialogComponent, {
    inputs: { event: makeEvent({ venueText: 'Kinosaal 9-133' }) },
    providers: [{ provide: OutcomeApi, useValue: { confirmLocation } }],
    on: { confirmed, closed },
  });
  return { view, confirmLocation, confirmed, closed };
}

describe('LocationDialogComponent', () => {
  it('warns that the place is public and shows it', async () => {
    await setup();
    expect(screen.getByText('Der Ort ist öffentlich. Keine Privatadresse.')).toBeInTheDocument();
    expect(screen.getByText('Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Ort ist öffentlich?' })).toBeInTheDocument();
  });

  it('confirms the building by default', async () => {
    const { confirmLocation, confirmed } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Ort bestätigen' }));
    expect(confirmLocation).toHaveBeenCalledWith('ev-1', 'building');
    expect(confirmed).toHaveBeenCalledWith(expect.objectContaining({ rev: 4 }));
  });

  it('confirms the exact place when chosen, never "hidden"', async () => {
    const { confirmLocation } = await setup();
    expect(screen.queryByRole('radio', { name: /versteckt/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: 'Genau' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ort bestätigen' }));
    expect(confirmLocation).toHaveBeenCalledWith('ev-1', 'exact');
  });

  it('keeps the dialog open on a refusal', async () => {
    const { confirmed } = await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Ort bestätigen' }));
    expect(confirmed).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
