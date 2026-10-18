import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { ReasonDialogComponent } from './reason-dialog.component';

const inputs = {
  heading: 'head.reinstateTitle' as const,
  subtitle: 'Movienight',
  label: 'head.reinstateReason' as const,
  confirm: 'head.reinstate' as const,
};

describe('ReasonDialogComponent', () => {
  it('needs a reason when it is required and sends it trimmed', async () => {
    const submitted = jest.fn();
    const { container } = await render(ReasonDialogComponent, { inputs, on: { submitted } });
    expect(screen.getByRole('dialog', { name: 'Absage zurücknehmen' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(screen.getByText('Bitte gib einen Grund an.')).toBeInTheDocument();
    expect(submitted).not.toHaveBeenCalled();
    await userEvent.type(
      screen.getByLabelText(/Warum nimmst du die Absage zurück/),
      '  Termin steht ',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(submitted).toHaveBeenCalledWith('Termin steht');
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('sends an empty note when the reason is optional', async () => {
    const submitted = jest.fn();
    await render(ReasonDialogComponent, {
      inputs: { ...inputs, required: false },
      on: { submitted },
    });
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(submitted).toHaveBeenCalledWith('');
  });

  it('refuses a reason over 500 characters and does not send while busy', async () => {
    const submitted = jest.fn();
    const { rerender } = await render(ReasonDialogComponent, { inputs, on: { submitted } });
    await userEvent.click(screen.getByLabelText(/Warum nimmst du die Absage zurück/));
    await userEvent.paste('x'.repeat(501));
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(submitted).not.toHaveBeenCalled();
    await rerender({ partialUpdate: true, inputs: { busy: true } });
    await userEvent.click(screen.getByRole('button', { name: 'Absage zurücknehmen' }));
    expect(submitted).not.toHaveBeenCalled();
  });

  it('closes from the cancel button', async () => {
    const closed = jest.fn();
    await render(ReasonDialogComponent, { inputs, on: { closed } });
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });
});
