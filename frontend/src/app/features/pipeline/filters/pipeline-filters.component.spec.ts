import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi } from '../../../../testing/event-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { NO_FILTERS, type PipelineFilters } from './pipeline-filters';
import { PipelineFiltersComponent } from './pipeline-filters.component';

async function setup(filters: PipelineFilters = NO_FILTERS, showView = false) {
  const api = fakeApi({
    allOrganizations: jest.fn(() =>
      of([{ id: 'o1', slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' }]),
    ),
    categories: jest.fn(() =>
      of([
        {
          id: 'c1',
          slug: 'film',
          name: 'Film',
          kind: 'format',
          children: [{ id: 'c2', slug: 'kino', name: 'Kino', kind: 'format' }],
        },
      ]),
    ),
  });
  const changed = jest.fn();
  const view = await render(PipelineFiltersComponent, {
    inputs: { filters, showView },
    providers: [{ provide: EventsApi, useValue: api }],
    on: { changed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, changed };
}

describe('PipelineFiltersComponent', () => {
  it('emits the next filters when the search text changes', async () => {
    const { changed } = await setup();
    await userEvent.setup().type(screen.getByRole('searchbox', { name: 'Events suchen' }), 'k');
    expect(changed).toHaveBeenCalledWith({ ...NO_FILTERS, q: 'k' });
  });

  it('chooses an organization, a category and a period from the chips', async () => {
    const { changed } = await setup();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /^Organisation/ }));
    await user.click(await screen.findByRole('option', { name: 'FSI' }));
    expect(changed).toHaveBeenLastCalledWith({ ...NO_FILTERS, organization: 'fsi' });
    await user.click(screen.getByRole('button', { name: /^Kategorie/ }));
    await user.click(await screen.findByRole('option', { name: 'Kino' }));
    expect(changed).toHaveBeenLastCalledWith({ ...NO_FILTERS, category: 'kino' });
    await user.click(screen.getByRole('button', { name: /^Zeitraum/ }));
    await user.click(await screen.findByRole('option', { name: 'Dieser Monat' }));
    expect(changed).toHaveBeenLastCalledWith({ ...NO_FILTERS, range: 'month' });
  });

  it('toggles "Nur meine" and tells the state', async () => {
    const { changed } = await setup({ ...NO_FILTERS, mine: true });
    const chip = screen.getByRole('button', { name: 'Nur meine' });
    expect(chip).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(chip);
    expect(changed).toHaveBeenCalledWith({ ...NO_FILTERS, mine: false });
  });

  it('offers no reset without a filter', async () => {
    await setup();
    expect(screen.queryByRole('button', { name: 'Filter zurücksetzen' })).not.toBeInTheDocument();
  });

  it('resets the filters and keeps the view', async () => {
    const { changed } = await setup({ ...NO_FILTERS, q: 'x', view: 'archived' }, true);
    await userEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }));
    expect(changed).toHaveBeenCalledWith({ ...NO_FILTERS, view: 'archived' });
  });

  it('switches the board view with the segmented control', async () => {
    const { changed } = await setup(NO_FILTERS, true);
    await userEvent.click(screen.getByRole('radio', { name: /Archiv/ }));
    expect(changed).toHaveBeenCalledWith({ ...NO_FILTERS, view: 'archived' });
  });

  it('has no axe violations', async () => {
    const { view } = await setup(NO_FILTERS, true);
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
