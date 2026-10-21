import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { CALENDAR_NOW } from '@shared/ui/calendar-grid/calendar-grid.component';
import { fakeApi } from '../../../../testing/event-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { CalendarApi } from '../api/calendar-api.service';
import type { CalendarEntry, CalendarOut } from '../model/calendar.models';
import { CalendarPageComponent } from './calendar-page.component';

const entry = (id: string, day: string): CalendarEntry => ({
  id,
  title: `Termin ${id}`,
  startsAt: `${day}T17:00:00Z`,
  endsAt: `${day}T19:00:00Z`,
  allDay: false,
  startsOn: day,
  endsOn: day,
  state: 'live',
  publicStatus: 'scheduled',
  organization: { slug: 'fsi', short: 'FSI', colorToken: 'petrol' },
  category: null,
  venueName: null,
  howtoUnverified: false,
});

function out(entries: CalendarEntry[], truncated = false): CalendarOut {
  return { from: '2026-09-28', to: '2026-11-08', entries, truncated };
}

describe('CalendarPageComponent', () => {
  async function setup(range = jest.fn(() => of(out([entry('a', '2026-10-20')])))) {
    const params = new BehaviorSubject(convertToParamMap({}));
    const view = await render(CalendarPageComponent, {
      providers: [
        provideRouter([]),
        { provide: CalendarApi, useValue: { range } },
        { provide: EventsApi, useValue: fakeApi() },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: params.value }, queryParamMap: params } },
        { provide: CALENDAR_NOW, useValue: () => new Date('2026-10-14T10:00:00Z') },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
    return { view, range, navigate };
  }

  it('asks for the 42-day range the grid shows, with the filters of the board', async () => {
    const { range } = await setup();
    await waitFor(() => expect(range).toHaveBeenCalled());
    expect(range).toHaveBeenCalledWith(
      expect.objectContaining({ from: '2026-09-28', to: '2026-11-08' }),
    );
    expect(screen.getByRole('heading', { level: 2, name: 'Oktober 2026' })).toBeInTheDocument();
    expect(await screen.findByText('Termin a')).toBeInTheDocument();
  });

  it('steps to the next month and back to today, and reloads that range', async () => {
    const { range } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Weiter' }));
    expect(await screen.findByRole('heading', { level: 2, name: 'November 2026' })).toBeInTheDocument();
    await waitFor(() =>
      expect(range).toHaveBeenLastCalledWith(expect.objectContaining({ from: '2026-10-26' })),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Heute' }));
    expect(await screen.findByRole('heading', { level: 2, name: 'Oktober 2026' })).toBeInTheDocument();
  });

  it('switches to the week and asks for seven days', async () => {
    const { range } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: 'Woche' }));
    await waitFor(() =>
      expect(range).toHaveBeenLastCalledWith(
        expect.objectContaining({ from: '2026-10-12', to: '2026-10-18' }),
      ),
    );
  });

  it('opens the dossier of a clicked entry', async () => {
    const { navigate } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: /Termin a/, hidden: true }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'a']);
  });

  it('says so when the list is cut off and when loading fails', async () => {
    await setup(jest.fn(() => of(out([], true))));
    expect(await screen.findByText(/mehr Termine, als hier stehen/)).toBeInTheDocument();
  });

  it('shows an error note when the endpoint fails', async () => {
    await setup(jest.fn(() => throwError(() => new Error('x'))));
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Kalender konnte nicht geladen werden.');
  });

  it('goes back to the list and keeps the query', async () => {
    const { navigate } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Liste' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers'], { queryParamsHandling: 'preserve' });
  });

  it('switches back from the week to the month', async () => {
    const { range } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: 'Woche' }));
    await userEvent.click(screen.getByRole('radio', { name: 'Monat' }));
    await waitFor(() =>
      expect(range).toHaveBeenLastCalledWith(expect.objectContaining({ from: '2026-09-28', to: '2026-11-08' })),
    );
  });
});
