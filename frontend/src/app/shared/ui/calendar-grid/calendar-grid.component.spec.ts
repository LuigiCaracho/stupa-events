import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { CALENDAR_NOW, CalendarGridComponent } from './calendar-grid.component';
import type { GridEntry } from './calendar-grid.util';

function entry(id: string, day: string, over: Partial<GridEntry> = {}): GridEntry {
  return {
    id,
    title: `Termin ${id}`,
    startsAt: `${day}T17:00:00Z`,
    startsOn: day,
    endsOn: day,
    allDay: false,
    state: 'published',
    publicStatus: 'scheduled',
    organization: { short: 'FSI', colorToken: 'petrol' },
    ...over,
  };
}

function setPhone(matches: boolean): void {
  window.matchMedia = ((query: string) => ({
    matches,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
}

describe('CalendarGridComponent', () => {
  const original = window.matchMedia;
  afterEach(() => (window.matchMedia = original));

  async function setup(entries: GridEntry[], extra: Record<string, unknown> = {}) {
    const rangeChange = jest.fn();
    const entryOpen = jest.fn();
    const anchorChange = jest.fn();
    const view = await render(CalendarGridComponent, {
      inputs: { entries, anchor: '2026-10-14', mode: 'month', ...extra },
      on: { rangeChange, entryOpen, anchorChange },
      providers: [{ provide: CALENDAR_NOW, useValue: () => new Date('2026-10-14T10:00:00Z') }],
    });
    return { view, rangeChange, entryOpen, anchorChange };
  }

  it('reports the 42-day range it shows and renders seven columns of weekday names', async () => {
    const { rangeChange } = await setup([]);
    expect(rangeChange).toHaveBeenCalledWith({ from: '2026-09-28', to: '2026-11-08' });
    expect(screen.getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Mo',
      'Di',
      'Mi',
      'Do',
      'Fr',
      'Sa',
      'So',
    ]);
    expect(screen.getAllByRole('gridcell')).toHaveLength(42);
  });

  it('marks today from the injected clock', async () => {
    await setup([]);
    const today = document.querySelector('[data-day="2026-10-14"]');
    expect(today).toHaveAttribute('aria-current', 'date');
    expect(document.querySelectorAll('[aria-current="date"]')).toHaveLength(1);
  });

  it('puts a multi-day entry on each day, all-day first, and shows "+n" after three', async () => {
    const trip = entry('trip', '2026-10-30', {
      allDay: true,
      endsOn: '2026-11-01',
      title: 'Skifahrt',
    });
    const day = Array.from({ length: 4 }, (_, i) => entry(`d${i}`, '2026-10-30'));
    await setup([...day, trip]);
    for (const key of ['2026-10-30', '2026-10-31', '2026-11-01']) {
      expect(
        within(document.querySelector(`[data-day="${key}"]`) as HTMLElement).getByText('Skifahrt'),
      ).toBeInTheDocument();
    }
    const cell = document.querySelector('[data-day="2026-10-30"]') as HTMLElement;
    expect(
      within(cell)
        .getAllByRole('button', { hidden: true })
        .map((b) => b.textContent)
        .join('|'),
    ).toContain('Skifahrt');
    expect(within(cell).getByRole('button', { name: '+2', hidden: true })).toBeInTheDocument();
  });

  it('opens an entry by click, and the day list in a sheet from "+n"', async () => {
    const day = Array.from({ length: 5 }, (_, i) => entry(`d${i}`, '2026-10-20'));
    const { entryOpen } = await setup(day);
    const cell = document.querySelector('[data-day="2026-10-20"]') as HTMLElement;
    await userEvent.click(within(cell).getByRole('button', { name: /Termin d0/, hidden: true }));
    expect(entryOpen).toHaveBeenCalledWith('d0');
    await userEvent.click(within(cell).getByRole('button', { name: '+2', hidden: true }));
    const sheet = await screen.findByRole('dialog', { name: 'Dienstag, 20. Oktober' });
    expect(within(sheet).getAllByRole('button', { name: /Termin/ })).toHaveLength(5);
    await userEvent.click(within(sheet).getByRole('button', { name: /Termin d4/ }));
    expect(entryOpen).toHaveBeenLastCalledWith('d4');
  });

  it('has one tab stop and moves with the arrow keys, asking for a new anchor at the edge', async () => {
    const { anchorChange } = await setup([]);
    const stops = document.querySelectorAll('[role="gridcell"][tabindex="0"]');
    expect(stops).toHaveLength(1);
    const start = stops[0] as HTMLElement;
    expect(start).toHaveAttribute('data-day', '2026-10-14');
    start.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(document.querySelector('[tabindex="0"]')).toHaveAttribute('data-day', '2026-10-15');
    await userEvent.keyboard('{ArrowDown}');
    expect(document.querySelector('[tabindex="0"]')).toHaveAttribute('data-day', '2026-10-22');
    await userEvent.keyboard('{Home}');
    expect(document.querySelector('[tabindex="0"]')).toHaveAttribute('data-day', '2026-10-19');
    await userEvent.keyboard('{End}{ArrowRight}');
    expect(document.querySelector('[tabindex="0"]')).toHaveAttribute('data-day', '2026-10-26');
    for (let i = 0; i < 3; i++) await userEvent.keyboard('{PageDown}');
    expect(anchorChange).toHaveBeenCalled();
  });

  it('moves the focus at once inside the grid, so a quick second key starts from the new day', async () => {
    await setup([]);
    const start = document.querySelector<HTMLElement>('[role="gridcell"][tabindex="0"]')!;
    start.focus();
    start.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(document.activeElement).toHaveAttribute('data-day', '2026-10-15');
    document.activeElement!.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }),
    );
    expect(document.activeElement).toHaveAttribute('data-day', '2026-10-14');
  });

  it('opens the only entry of a day with Enter and the sheet when there are several', async () => {
    const { entryOpen } = await setup([
      entry('one', '2026-10-14'),
      entry('a', '2026-10-15'),
      entry('b', '2026-10-15'),
    ]);
    (document.querySelector('[data-day="2026-10-14"]') as HTMLElement).focus();
    await userEvent.keyboard('{Enter}');
    expect(entryOpen).toHaveBeenCalledWith('one');
    await userEvent.keyboard('{ArrowRight}{Enter}');
    expect(
      await screen.findByRole('dialog', { name: 'Donnerstag, 15. Oktober' }),
    ).toBeInTheDocument();
  });

  it('shows the full day list per column in the week mode', async () => {
    const day = Array.from({ length: 5 }, (_, i) => entry(`d${i}`, '2026-10-14'));
    const { rangeChange } = await setup(day, { mode: 'week' });
    expect(rangeChange).toHaveBeenCalledWith({ from: '2026-10-12', to: '2026-10-18' });
    expect(screen.getAllByRole('gridcell')).toHaveLength(7);
    expect(screen.queryByText(/^\+\d/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Termin d\d/)).toHaveLength(5);
  });

  it('is an agenda list per day under 768 px, with only the days that have entries', async () => {
    setPhone(true);
    const { entryOpen } = await setup([entry('a', '2026-10-20'), entry('b', '2026-10-22')]);
    expect(screen.queryByRole('grid')).not.toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent?.trim())).toEqual([
      'Di., 20. Okt.',
      'Do., 22. Okt.',
    ]);
    await userEvent.click(screen.getByRole('button', { name: /Termin b/ }));
    expect(entryOpen).toHaveBeenCalledWith('b');
  });

  it('says so when the agenda is empty', async () => {
    setPhone(true);
    await setup([]);
    expect(screen.getByRole('status')).toHaveTextContent('Keine Termine in diesem Zeitraum.');
  });

  it('moves "today" on when the clock passes midnight', async () => {
    jest.useFakeTimers();
    let now = new Date('2026-10-14T21:59:00Z');
    const view = await render(CalendarGridComponent, {
      inputs: { entries: [], anchor: '2026-10-14', mode: 'month' },
      providers: [{ provide: CALENDAR_NOW, useValue: () => now }],
    });
    expect(document.querySelector('[aria-current="date"]')).toHaveAttribute(
      'data-day',
      '2026-10-14',
    );
    now = new Date('2026-10-14T22:01:00Z');
    jest.advanceTimersByTime(61_000);
    view.fixture.detectChanges();
    expect(document.querySelector('[aria-current="date"]')).toHaveAttribute(
      'data-day',
      '2026-10-15',
    );
    jest.useRealTimers();
  });

  it('has no axe violations as a grid', async () => {
    const { view } = await setup([entry('a', '2026-10-20'), entry('b', '2026-10-20')]);
    expect(await runAxe(view.container)).toHaveNoViolations();
  }, 30_000);

  it('has no axe violations as an agenda', async () => {
    setPhone(true);
    const { view } = await setup([entry('a', '2026-10-20')]);
    expect(await runAxe(view.container)).toHaveNoViolations();
  }, 30_000);

  it('reports a range only when it changes, not for another day of the same month', async () => {
    const { view, rangeChange } = await setup([]);
    expect(rangeChange).toHaveBeenCalledTimes(1);
    view.fixture.componentRef.setInput('anchor', '2026-10-20');
    view.fixture.detectChanges();
    expect(rangeChange).toHaveBeenCalledTimes(1);
    view.fixture.componentRef.setInput('anchor', '2026-11-03');
    view.fixture.detectChanges();
    expect(rangeChange).toHaveBeenCalledTimes(2);
    expect(rangeChange).toHaveBeenLastCalledWith({ from: '2026-10-26', to: '2026-12-06' });
  });

  it('does nothing on Enter in an empty day and opens a day with Space', async () => {
    const { entryOpen } = await setup([entry('x', '2026-10-15')]);
    (document.querySelector('[data-day="2026-10-14"]') as HTMLElement).focus();
    await userEvent.keyboard('{Enter}');
    expect(entryOpen).not.toHaveBeenCalled();
    await userEvent.keyboard('{ArrowRight}{ }');
    expect(entryOpen).toHaveBeenCalledWith('x');
  });

  it('keeps "today" when the clock ticks inside the same day', async () => {
    jest.useFakeTimers();
    const now = new Date('2026-10-14T10:00:00Z');
    const view = await render(CalendarGridComponent, {
      inputs: { entries: [], anchor: '2026-10-14', mode: 'month' },
      providers: [{ provide: CALENDAR_NOW, useValue: () => now }],
    });
    jest.advanceTimersByTime(61_000);
    view.fixture.detectChanges();
    expect(document.querySelector('[aria-current="date"]')).toHaveAttribute(
      'data-day',
      '2026-10-14',
    );
    jest.useRealTimers();
  });

  it('ignores a key that has no meaning in the grid', async () => {
    const { anchorChange } = await setup([]);
    (document.querySelector('[data-day="2026-10-14"]') as HTMLElement).focus();
    await userEvent.keyboard('a');
    expect(anchorChange).not.toHaveBeenCalled();
    expect(document.querySelector('[tabindex="0"]')).toHaveAttribute('data-day', '2026-10-14');
  });
});
