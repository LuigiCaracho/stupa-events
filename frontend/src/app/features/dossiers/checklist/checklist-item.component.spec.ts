import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import type { ChecklistItemOut } from '../model/checklist.models';
import { ChecklistItemComponent } from './checklist-item.component';

const item = (o: Partial<ChecklistItemOut> = {}): ChecklistItemOut => ({
  id: 'c1',
  text: 'Raum buchen',
  phase: 'planning',
  required: true,
  position: 1,
  assigneeSub: 'u1',
  assigneeName: 'Anna',
  dueAt: '2026-11-01T10:00:00Z',
  dueOffsetDays: -28,
  dueManual: false,
  overdue: false,
  doneAt: null,
  doneBy: null,
  waivedReason: null,
  fromTemplate: true,
  ...o,
});

async function setup(i: ChecklistItemOut, inputs: Record<string, unknown> = {}) {
  const command = jest.fn();
  const view = await render(ChecklistItemComponent, {
    inputs: {
      item: i,
      canEdit: true,
      canTick: true,
      assignees: [
        { value: 'u1', label: 'Anna' },
        { value: 'u2', label: 'Ben' },
      ],
      ...inputs,
    },
    on: { command },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, command };
}

describe('ChecklistItemComponent', () => {
  it('shows "Pflicht", the assignee and the due chip as relative and absolute text', async () => {
    const { container } = await setup(item());
    expect(screen.getByText('Pflicht')).toBeInTheDocument();
    expect(screen.getByText('Anna')).toBeInTheDocument();
    expect(screen.getByText('4 Wochen vorher')).toBeInTheDocument();
    expect(screen.getByText(/01\.11\.2026|1\. Nov/)).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('says "überfällig" as text', async () => {
    await setup(item({ overdue: true, required: false }));
    expect(screen.getByText('überfällig')).toBeInTheDocument();
    expect(screen.queryByText('Pflicht')).not.toBeInTheDocument();
  });

  it('ticks and unticks', async () => {
    const { command } = await setup(item());
    await userEvent.click(screen.getByRole('checkbox', { name: /Raum buchen/ }));
    expect(command).toHaveBeenCalledWith({ name: 'done', done: true });
  });

  it('cannot be ticked without the right, nor when waived', async () => {
    await setup(item({ waivedReason: 'entfällt, weil kein Raum nötig' }), {
      canTick: false,
      canEdit: false,
    });
    expect(screen.getByRole('checkbox', { name: /Raum buchen/ })).toBeDisabled();
    expect(screen.getByText(/Entfällt: entfällt, weil/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Aktionen für den Punkt' }),
    ).not.toBeInTheDocument();
  });

  it('waives a required point only with a reason of ten characters', async () => {
    const { command } = await setup(item());
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Entfällt mit Grund' }));
    expect(
      screen.getByText('Ein Pflichtpunkt braucht einen Grund mit mindestens 10 Zeichen.'),
    ).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Entfällt' });
    await userEvent.type(screen.getByLabelText('Grund'), 'kurz');
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Grund'), ' und lang genug');
    await userEvent.click(confirm);
    expect(command).toHaveBeenCalledWith({ name: 'waive', reason: 'kurz und lang genug' });
  });

  it('waives an optional point with any reason and can cancel', async () => {
    const { command } = await setup(item({ required: false }));
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Entfällt mit Grund' }));
    await userEvent.click(screen.getByRole('button', { name: 'Entfällt' }));
    expect(command).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText('Grund'), 'nö');
    await userEvent.click(screen.getByRole('button', { name: 'Entfällt' }));
    expect(command).toHaveBeenCalledWith({ name: 'waive', reason: 'nö' });
  });

  it('assigns a person or clears the assignment and can cancel', async () => {
    const { command } = await setup(item());
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Zuweisen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Zuweisen' }));
    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(await screen.findByRole('option', { name: 'Ben' }));
    expect(command).toHaveBeenCalledWith({ name: 'assign', sub: 'u2' });
  });

  it('deletes only a point that is not from a template', async () => {
    const { command, fixture } = await setup(item({ fromTemplate: true }));
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    expect(screen.queryByRole('menuitem', { name: 'Löschen' })).not.toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    fixture.componentRef.setInput('item', item({ fromTemplate: false }));
    fixture.detectChanges();
    await userEvent.click(screen.getByRole('button', { name: 'Aktionen für den Punkt' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Löschen' }));
    expect(command).toHaveBeenCalledWith({ name: 'delete' });
  });
});
