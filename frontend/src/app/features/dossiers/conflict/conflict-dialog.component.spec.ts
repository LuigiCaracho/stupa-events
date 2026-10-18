import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { ConflictDialogComponent } from './conflict-dialog.component';

const current = makeEvent({ summary: 'Neu von jemand', rev: 9 });
const base = { summary: 'Alt', title: 'Movienight', startsAt: '2026-11-05T18:00:00Z' };

async function setup(inputs: Record<string, unknown> = {}) {
  const keep = jest.fn();
  const reload = jest.fn();
  const closed = jest.fn();
  const view = await render(ConflictDialogComponent, {
    inputs: { current, mine: { summary: 'Von mir', title: 'Filmabend' }, base, ...inputs },
    on: { keep, reload, closed },
  });
  return { view, keep, reload, closed };
}

describe('ConflictDialogComponent', () => {
  it('shows base, own and current value in three columns', async () => {
    await setup();
    const dialog = screen.getByRole('dialog', { name: 'Jemand anderes war schneller' });
    expect(within(dialog).getByText('Ausgangsstand')).toBeInTheDocument();
    expect(within(dialog).getByText('Deins')).toBeInTheDocument();
    const row = within(dialog).getByText('Kurztext', { selector: '.cf__label' }).closest('li')!;
    expect(row).toHaveTextContent('Alt');
    expect(row).toHaveTextContent('Von mir');
    expect(row).toHaveTextContent('Neu von jemand');
    expect(within(dialog).getByText('Das hat sich inzwischen geändert')).toBeInTheDocument();
  });

  it('keeps the uncontested change and takes the other value for the contested field by default', async () => {
    const { keep } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(keep).toHaveBeenCalledWith({ title: 'Filmabend' });
  });

  it('keeps the own value of a contested field on request', async () => {
    const { keep } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: /Deins behalten/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(keep).toHaveBeenCalledWith({ summary: 'Von mir', title: 'Filmabend' });
    await userEvent.click(screen.getByRole('radio', { name: /Neu übernehmen/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(keep).toHaveBeenLastCalledWith({ title: 'Filmabend' });
  });

  it('works without a base: no server diff and no choice', async () => {
    await setup({ base: null });
    expect(screen.queryByText('Das hat sich inzwischen geändert')).not.toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.getAllByText('–').length).toBeGreaterThan(0);
  });

  it('shows names for a venue and a category and "(leer)" for nothing', async () => {
    await setup({
      mine: { venueId: 'v1', primaryCategoryId: 'cat-9', costText: null },
      venues: [{ id: 'v1', slug: 'k', name: 'Kinosaal' }],
      categories: [{ id: 'cat-9', slug: 'x', name: 'Konzert', kind: 'format' }],
      base: {},
    });
    expect(screen.getByText('Kinosaal')).toBeInTheDocument();
    expect(screen.getByText('Konzert')).toBeInTheDocument();
    expect(screen.getAllByText('(leer)').length).toBeGreaterThan(0);
  });

  it('reloads and closes', async () => {
    const { reload, closed } = await setup();
    await userEvent.click(
      screen.getByRole('button', { name: 'Neu laden, meine Änderungen verwerfen' }),
    );
    expect(reload).toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Schließen' }));
    expect(closed).toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
  });
});
