import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { CalendarEntryComponent } from './calendar-entry.component';
import type { GridEntry } from './calendar-grid.util';

const entry = (over: Partial<GridEntry> = {}): GridEntry => ({
  id: 'e1',
  title: 'Movienight',
  startsAt: '2026-10-29T17:00:00Z',
  startsOn: '2026-10-29',
  endsOn: '2026-10-29',
  allDay: false,
  state: 'live',
  publicStatus: 'scheduled',
  organization: { short: 'FSI', colorToken: 'petrol' },
  ...over,
});

describe('CalendarEntryComponent', () => {
  it('shows time in Berlin, title and organization, and no state text for a live entry', async () => {
    await render(CalendarEntryComponent, { inputs: { entry: entry() } });
    expect(screen.getByText('18:00')).toBeInTheDocument();
    expect(screen.getByText('Movienight')).toBeInTheDocument();
    expect(screen.getByText('FSI')).toBeInTheDocument();
    expect(screen.queryByText('Idee')).not.toBeInTheDocument();
  });

  it('writes the state as text for everything but live and approved, and the cancellation first', async () => {
    const view = await render(CalendarEntryComponent, { inputs: { entry: entry({ state: 'planning' }) } });
    expect(screen.getByText('Planung')).toBeInTheDocument();
    view.fixture.componentRef.setInput('entry', entry({ state: 'live', publicStatus: 'cancelled' }));
    view.fixture.detectChanges();
    expect(screen.getByText('Abgesagt')).toBeInTheDocument();
    view.fixture.componentRef.setInput('entry', entry({ state: 'approved' }));
    view.fixture.detectChanges();
    expect(screen.queryByText('Planung')).not.toBeInTheDocument();
    expect(screen.queryByText('Abgesagt')).not.toBeInTheDocument();
  });

  it('shows "ganztägig" for an all-day entry and a continuation marker on later days', async () => {
    const view = await render(CalendarEntryComponent, {
      inputs: { entry: entry({ allDay: true, startsOn: '2026-10-30', endsOn: '2026-11-01' }), day: '2026-10-30' },
    });
    expect(screen.getByText('ganztägig')).toBeInTheDocument();
    view.fixture.componentRef.setInput('day', '2026-10-31');
    view.fixture.detectChanges();
    expect(screen.getByText('weiter')).toBeInTheDocument();
  });

  it('warns about an unverified howto and keeps the button out of the tab order in a grid', async () => {
    await render(CalendarEntryComponent, {
      inputs: { entry: entry({ howtoUnverified: true }), focusable: false },
    });
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
    expect(screen.getByRole('button')).toHaveAttribute('tabindex', '-1');
  });

  it('opens with the id and does not bubble the click', async () => {
    const open = jest.fn();
    await render(CalendarEntryComponent, { inputs: { entry: entry() }, on: { open } });
    await userEvent.click(screen.getByRole('button'));
    expect(open).toHaveBeenCalledWith('e1');
  });

  it('writes "Verschoben" for a postponed entry and falls back to a neutral stripe without a colour token', async () => {
    const { container } = await render(CalendarEntryComponent, {
      inputs: { entry: entry({ publicStatus: 'postponed', organization: { short: 'FSI', colorToken: null } }) },
    });
    expect(screen.getByText('Verschoben')).toBeInTheDocument();
    expect(container.querySelector('button')?.getAttribute('style')).toContain('--color-border-strong');
  });
});
