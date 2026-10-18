import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeCard } from '../../../../testing/event-fixtures';
import { MoveSheetComponent } from './move-sheet.component';

describe('MoveSheetComponent', () => {
  it('offers the human transitions of the card and reports the choice', async () => {
    const chosen = jest.fn();
    await render(MoveSheetComponent, {
      inputs: { card: makeCard({ allowedTransitions: ['T02', 'T11', 'T08'] }) },
      on: { chosen },
    });
    expect(screen.getByRole('dialog', { name: 'Verschieben' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Nachbereitung (automatisch)' }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
    expect(chosen).toHaveBeenCalledWith('T11');
    expect(screen.getByRole('button', { name: 'Freigabe anfragen' })).toBeInTheDocument();
  });

  it('says so when nothing is possible and has no axe violations', async () => {
    const { container } = await render(MoveSheetComponent, {
      inputs: { card: makeCard({ allowedTransitions: [] }) },
    });
    expect(screen.getByText('Gerade ist kein Übergang möglich.')).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
