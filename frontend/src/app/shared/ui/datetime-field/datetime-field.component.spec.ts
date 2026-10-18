import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { DatetimeFieldComponent } from './datetime-field.component';

describe('DatetimeFieldComponent', () => {
  const inputs = { dateLabel: 'Beginn, Datum', timeLabel: 'Beginn, Uhrzeit' };

  it('reports the typed date and time through its two-way values', async () => {
    const { container, fixture } = await render(DatetimeFieldComponent, { inputs });
    await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:30');
    await userEvent.tab();
    expect(fixture.componentInstance.date()).toBe('2026-11-05');
    expect(fixture.componentInstance.time()).toBe('19:30');
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('shows the values it is given and can be disabled', async () => {
    const { fixture } = await render(DatetimeFieldComponent, {
      inputs: { ...inputs, date: '2026-11-05', time: '19:30', disabled: true, error: 'Fehler' },
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(screen.getByLabelText(/Beginn, Datum/)).toBeDisabled();
    expect(screen.getByLabelText(/Beginn, Uhrzeit/)).toHaveValue('19:30');
    expect(screen.getByRole('alert')).toHaveTextContent('Fehler');
  });
});
