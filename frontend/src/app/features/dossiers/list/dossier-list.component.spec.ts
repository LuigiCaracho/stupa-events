import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { AuthService } from '@core/auth/auth.service';
import { fakeApi, fakeAuth, makeCard } from '../../../../testing/event-fixtures';
import { convertToParamMap } from '@angular/router';
import { EventsApi } from '../api/events-api.service';
import { DossierListComponent } from './dossier-list.component';

describe('DossierListComponent', () => {
  async function setup(
    api = fakeApi(),
    data: Record<string, unknown> = {},
    child: string | null = null,
  ) {
    const params = new BehaviorSubject(convertToParamMap({}));
    const route = {
      snapshot: { data, queryParamMap: params.value },
      queryParamMap: params,
      firstChild: child ? { snapshot: { paramMap: convertToParamMap({ id: child }) } } : null,
    };
    const view = await render(DossierListComponent, {
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EventsApi, useValue: api },
        { provide: ActivatedRoute, useValue: route },
        { provide: AuthService, useValue: fakeAuth() },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
    const navigateByUrl = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    return { view, api, navigate, navigateByUrl };
  }

  it('renders one row per dossier with day, state, organization, venue and blockers', async () => {
    const api = fakeApi({
      listCards: jest.fn(() =>
        of({ items: [makeCard({ blockerCount: 2 })], total: 1, limit: 100, offset: 0 }),
      ),
    });
    await setup(api);
    const link = await screen.findByRole('link', { name: 'Movienight' });
    expect(link).toHaveAttribute('href', '/dossiers/ev-1');
    expect(screen.getByText('Planung')).toBeInTheDocument();
    expect(screen.getByText('FSI · Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('Do., 5. Nov.')).toBeInTheDocument();
    expect(screen.getByText('2 offen')).toBeInTheDocument();
    expect(screen.getByText('1 Dossiers')).toBeInTheDocument();
  });

  it('uses the shared pane header with the h1, and hands the h1 to the open dossier', async () => {
    const { view } = await setup();
    expect(view.container.querySelectorAll('h1')).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1, name: 'Dossiers' })).toBeInTheDocument();
    view.fixture.destroy();
  });

  it('shows the title as plain text while a dossier is open', async () => {
    const { view } = await setup(fakeApi(), {}, 'ev-1');
    expect(view.container.querySelectorAll('h1')).toHaveLength(0);
    expect(view.container.querySelector('p.ph__title')).toHaveTextContent('Dossiers');
  });

  it('searches live after a short delay with the filters of the board', async () => {
    const { api } = await setup();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Events suchen' }), 'kino');
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: 'kino', limit: 100 }),
      ),
    );
  });

  it('offers to reset the filters when nothing matches and the first event when there is nothing', async () => {
    const api = fakeApi({
      listCards: jest.fn(() => of({ items: [], total: 0, limit: 100, offset: 0 })),
    });
    const { navigateByUrl } = await setup(api);
    expect(await screen.findByText('Noch keine Dossiers.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' }).at(-1)!);
    expect(navigateByUrl).toHaveBeenCalledWith('/dossiers/neu');
    await userEvent.type(screen.getByRole('searchbox', { name: 'Events suchen' }), 'x');
    expect(await screen.findByText('Keine Dossiers für diese Filter.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Filter zurücksetzen' })[0]);
    expect(await screen.findByText('Noch keine Dossiers.')).toBeInTheDocument();
  });

  it('loads more rows on request', async () => {
    const api = fakeApi({
      listCards: jest.fn(() => of({ items: [makeCard()], total: 150, limit: 100, offset: 0 })),
    });
    await setup(api);
    await userEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }));
    await waitFor(() =>
      expect(api.listCards).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 200 })),
    );
  });

  it('shows an error note when the load fails', async () => {
    await setup(
      fakeApi({
        listCards: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Dossiers konnten nicht geladen werden.',
    );
  });

  it('marks the open dossier in the list and hints at the choice beside it', async () => {
    await setup(fakeApi(), {}, 'ev-1');
    expect(await screen.findByRole('link', { name: 'Movienight', hidden: true })).toHaveAttribute(
      'aria-current',
      'true',
    );
  });

  it('does not fail while the child route has no snapshot yet', async () => {
    const params = new BehaviorSubject(convertToParamMap({}));
    const route = {
      snapshot: { data: {}, queryParamMap: params.value },
      queryParamMap: params,
      firstChild: {},
    };
    await render(DossierListComponent, {
      providers: [
        provideRouter([]),
        { provide: EventsApi, useValue: fakeApi() },
        { provide: ActivatedRoute, useValue: route },
        { provide: AuthService, useValue: fakeAuth() },
      ],
    });
    expect(await screen.findByText('Wähle ein Dossier aus der Liste.')).toBeInTheDocument();
  });

  it('asks to pick a dossier when none is open', async () => {
    await setup();
    expect(await screen.findByText('Wähle ein Dossier aus der Liste.')).toBeInTheDocument();
  });

  it('opens the dialog on the new-event route and closes it back to the list', async () => {
    const { navigateByUrl } = await setup(fakeApi(), { newEvent: true });
    expect(await screen.findByRole('dialog', { name: 'Neues Event' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Schließen' }));
    expect(navigateByUrl).toHaveBeenCalledWith('/dossiers');
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

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('link', { name: 'Movienight' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  describe('M5', () => {
    it('warns in text on a row whose archived howto is unchecked', async () => {
      const api = fakeApi({
        listCards: jest.fn(() =>
          of({ items: [makeCard({ state: 'archived', howtoUnverified: true })], total: 1, limit: 100, offset: 0 }),
        ),
      });
      await setup(api);
      expect(await screen.findByText('Anleitung ungeprüft')).toBeInTheDocument();
    });

    it('leads to the calendar and keeps the filters', async () => {
      const { navigate } = await setup();
      await userEvent.click(screen.getAllByRole('button', { name: 'Kalender' })[0]);
      expect(navigate).toHaveBeenCalledWith(['/kalender'], { queryParamsHandling: 'preserve' });
    });

    it('opens the blank dialog on /dossiers/neu and switches to "Aus Vorlage"', async () => {
      await setup(fakeApi(), { newEvent: true });
      expect(await screen.findByRole('dialog', { name: 'Neues Event' })).toBeInTheDocument();
      await userEvent.click(screen.getByRole('radio', { name: 'Aus Vorlage' }));
      expect(await screen.findByRole('dialog', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
    });
  });
});
