import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, makeCard } from '../../../../testing/event-fixtures';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { CalendarApi } from '../../calendar/api/calendar-api.service';
import { FormatsApi } from '../../formats/api/formats-api.service';
import { AttachmentsApi } from '../api/attachments-api.service';
import { EventsApi } from '../api/events-api.service';
import { DossierListComponent } from './dossier-list.component';

const EMPTY_PAGE = { items: [], total: 0, limit: 50, offset: 0 };

describe('DossierListComponent', () => {
  async function setup(
    api = fakeApi(),
    data: Record<string, unknown> = {},
    query: Record<string, string> = {},
  ) {
    const params = new BehaviorSubject(convertToParamMap(query));
    const route = { snapshot: { data, queryParamMap: params.value }, queryParamMap: params };
    const archive = { templates: jest.fn(() => of(EMPTY_PAGE)), clonePreview: jest.fn() };
    const calendar = { range: jest.fn(() => of({ from: '', to: '', entries: [], truncated: false })) };
    const view = await render(DossierListComponent, {
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EventsApi, useValue: api },
        { provide: CalendarApi, useValue: calendar },
        { provide: ArchiveApi, useValue: archive },
        { provide: FormatsApi, useValue: { list: jest.fn(() => of(EMPTY_PAGE)) } },
        { provide: AttachmentsApi, useValue: { quotes: jest.fn(() => of({ groups: [] })) } },
        { provide: ActivatedRoute, useValue: route },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
    const navigateByUrl = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    return { view, api, calendar, navigate, navigateByUrl };
  }

  it('renders one card per event with day, state, organization, venue and the count', async () => {
    const api = fakeApi({
      listCards: jest.fn(() =>
        of({ items: [makeCard({ hasPoster: true })], total: 1, limit: 50, offset: 0 }),
      ),
    });
    await setup(api);
    const link = await screen.findByRole('link', { name: 'Movienight' });
    expect(link).toHaveAttribute('href', '/dossiers/ev-1');
    expect(screen.getByText('Entwurf')).toBeInTheDocument();
    expect(screen.getByText('FSI · Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('Do., 5. Nov.')).toBeInTheDocument();
    expect(screen.getByText('1 Events')).toBeInTheDocument();
  });

  it('shows a picture thumbnail where there is a poster and warns where a published event has none', async () => {
    const api = fakeApi({
      listCards: jest.fn(() =>
        of({
          items: [
            makeCard({ id: 'a', title: 'Mit Bild', state: 'published', hasPoster: true }),
            makeCard({ id: 'b', title: 'Ohne', state: 'published', hasPoster: false }),
            makeCard({ id: 'c', title: 'Entwurf', state: 'draft', hasPoster: false }),
          ],
          total: 3,
          limit: 50,
          offset: 0,
        }),
      ),
    });
    const { view } = await setup(api);
    await screen.findByRole('link', { name: 'Mit Bild' });
    expect(view.container.querySelectorAll('img.ec__img')).toHaveLength(1);
    expect(screen.getAllByText('Ohne Bild')).toHaveLength(1);
  });

  it('puts "Neues Event" and "Neu aus Vorlage" side by side in the header', async () => {
    const { navigateByUrl } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Neues Event' }));
    expect(navigateByUrl).toHaveBeenLastCalledWith('/dossiers/neu');
    await userEvent.click(screen.getByRole('button', { name: 'Neu aus Vorlage' }));
    expect(navigateByUrl).toHaveBeenLastCalledWith('/dossiers/neu?modus=vorlage');
  });

  it('asks for the active states by default and for one state when its chip is set', async () => {
    const { api } = await setup();
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(
        expect.objectContaining({ state: ['draft', 'published'], limit: 50 }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: /^Zustand/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Archiv' }));
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(
        expect.objectContaining({ state: ['archived'], sort: '-startsAt' }),
      ),
    );
  });

  it('keeps only cancelled events for the chip "Abgesagt"', async () => {
    const api = fakeApi({
      listCards: jest.fn(() =>
        of({
          items: [
            makeCard({ id: 'a', title: 'Läuft', state: 'published' }),
            makeCard({ id: 'b', title: 'Fällt aus', state: 'published', publicStatus: 'cancelled' }),
          ],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      ),
    });
    await setup(api, {}, { zustand: 'cancelled' });
    expect(await screen.findByRole('link', { name: 'Fällt aus' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Läuft' })).not.toBeInTheDocument();
  });

  it('searches live after a short delay', async () => {
    const { api } = await setup();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Events suchen' }), 'kino');
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'kino' })),
    );
  });

  it('offers to reset the filters when nothing matches and the first event when there is nothing', async () => {
    const api = fakeApi({
      listCards: jest.fn(() => of({ items: [], total: 0, limit: 50, offset: 0 })),
    });
    const { navigateByUrl } = await setup(api);
    expect(await screen.findByText('Noch keine Events.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' }).at(-1)!);
    expect(navigateByUrl).toHaveBeenCalledWith('/dossiers/neu');
    await userEvent.type(screen.getByRole('searchbox', { name: 'Events suchen' }), 'x');
    expect(await screen.findByText('Keine Events für diese Filter.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Filter zurücksetzen' })[0]);
    expect(await screen.findByText('Noch keine Events.')).toBeInTheDocument();
  });

  it('loads more rows on request', async () => {
    const api = fakeApi({
      listCards: jest.fn(() => of({ items: [makeCard()], total: 150, limit: 50, offset: 0 })),
    });
    await setup(api);
    await userEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }));
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 100 })),
    );
  });

  it('shows an error note when the load fails', async () => {
    await setup(
      fakeApi({
        listCards: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Events konnten nicht geladen werden.',
    );
  });

  it('warns in text on a card whose archived howto is unchecked', async () => {
    const api = fakeApi({
      listCards: jest.fn(() =>
        of({
          items: [makeCard({ state: 'archived', howtoUnverified: true })],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      ),
    });
    await setup(api);
    expect(await screen.findByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('switches to the calendar, keeps the filters and writes the view into the URL', async () => {
    const { api, calendar, navigate } = await setup(fakeApi(), {}, { org: 'fsi' });
    await userEvent.click(screen.getByRole('radio', { name: 'Kalender' }));
    expect(navigate).toHaveBeenLastCalledWith(
      [],
      expect.objectContaining({
        queryParams: expect.objectContaining({ ansicht: 'kalender', org: 'fsi' }),
      }),
    );
    await waitFor(() =>
      expect(calendar.range).toHaveBeenCalledWith(expect.objectContaining({ organization: 'fsi' })),
    );
    expect(screen.queryByRole('link', { name: 'Movienight' })).not.toBeInTheDocument();
    expect(api.listCards).toHaveBeenCalledTimes(1);
  });

  it('opens the calendar straight from ?ansicht=kalender', async () => {
    const { calendar, api } = await setup(fakeApi(), {}, { ansicht: 'kalender' });
    await waitFor(() => expect(calendar.range).toHaveBeenCalled());
    expect(api.listCards).not.toHaveBeenCalled();
  });

  it('opens the dialog on the new-event route and closes it back to the list', async () => {
    const { navigateByUrl } = await setup(fakeApi(), { newEvent: true });
    expect(await screen.findByRole('dialog', { name: 'Neues Event' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Schließen' }));
    expect(navigateByUrl).toHaveBeenCalledWith('/dossiers');
  });

  it('opens the blank dialog on /dossiers/neu and switches to "Aus Vorlage"', async () => {
    await setup(fakeApi(), { newEvent: true });
    expect(await screen.findByRole('dialog', { name: 'Neues Event' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('radio', { name: 'Aus Vorlage' }));
    expect(await screen.findByRole('dialog', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
  });

  it('starts on the template tab for ?modus=vorlage', async () => {
    await setup(fakeApi(), { newEvent: true }, { modus: 'vorlage' });
    expect(await screen.findByRole('dialog', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
  });

  it('opens the created dossier', async () => {
    const { navigate } = await setup(fakeApi(), { newEvent: true });
    await screen.findByRole('dialog', { name: 'Neues Event' });
    await userEvent.type(screen.getByLabelText(/^Titel/), 'Neu');
    await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2099');
    await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:00');
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith(['/dossiers', 'ev-1']));
  });

  it('has the one h1 "Events" and no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('link', { name: 'Movienight' });
    expect(screen.getByRole('heading', { level: 1, name: 'Events' })).toBeInTheDocument();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
