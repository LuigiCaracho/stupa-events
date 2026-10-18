import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { EventsApi } from '../api/events-api.service';
import { fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import { DossierListComponent } from './dossier-list.component';

describe('DossierListComponent', () => {
  async function setup(api = fakeApi(), data: Record<string, unknown> = {}) {
    const view = await render(DossierListComponent, {
      providers: [
        provideRouter([]),
        { provide: EventsApi, useValue: api },
        { provide: AuthService, useValue: fakeAuth() },
        { provide: ActivatedRoute, useValue: { snapshot: { data } } },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    return { view, api };
  }

  it('renders one row per dossier with state, organization and venue', async () => {
    await setup();
    const link = await screen.findByRole('link', { name: 'Movienight' });
    expect(link).toHaveAttribute('href', '/dossiers/ev-1');
    expect(screen.getByText('Planung')).toBeInTheDocument();
    expect(screen.getByText('FSI · Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('1 Dossiers')).toBeInTheDocument();
  });

  it('searches live after a short delay and filters by state', async () => {
    const { api } = await setup();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Titel suchen' }), 'kino');
    await waitFor(() => expect(api.list).toHaveBeenLastCalledWith({ q: 'kino', state: undefined, limit: 200 }));
    await userEvent.click(screen.getByRole('combobox', { name: 'Zustand' }));
    await userEvent.click(screen.getByRole('option', { name: 'Freigabe' }));
    await waitFor(() => expect(api.list).toHaveBeenLastCalledWith({ q: 'kino', state: 'in_review', limit: 200 }));
  });

  it('offers to reset the filters when nothing matches', async () => {
    const api = fakeApi({ list: jest.fn(() => of({ items: [], total: 0, limit: 200, offset: 0 })) });
    await setup(api);
    expect(await screen.findByText('Noch keine Dossiers.')).toBeInTheDocument();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Titel suchen' }), 'x');
    expect(await screen.findByText('Keine Dossiers für diese Filter.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }));
    expect(await screen.findByText('Noch keine Dossiers.')).toBeInTheDocument();
  });

  it('shows an error note when the list cannot be loaded', async () => {
    await setup(fakeApi({ list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Dossiers konnten nicht geladen werden.');
  });

  it('goes to the new-event route from the header button', async () => {
    const { view } = await setup();
    const navigate = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigateByUrl').mockResolvedValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'Neues Event' }));
    expect(navigate).toHaveBeenCalledWith('/dossiers/neu');
  });

  it('opens the dialog on the new route and opens the created dossier', async () => {
    const { view } = await setup(fakeApi({ list: jest.fn(() => of({ items: [makeEvent({ state: 'idea' })], total: 1, limit: 200, offset: 0 })) }), { newEvent: true });
    const navigate = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigate').mockResolvedValue(true);
    expect(await screen.findByRole('dialog', { name: 'Neues Event' })).toBeInTheDocument();
    const close = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigateByUrl').mockResolvedValue(true);
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(close).toHaveBeenCalledWith('/dossiers');
    expect(navigate).not.toHaveBeenCalled();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('link', { name: 'Movienight' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('opens a created dossier', async () => {
    const { view } = await setup();
    const navigate = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigate').mockResolvedValue(true);
    (view.fixture.componentInstance as unknown as { opened(e: unknown): void }).opened(makeEvent({ id: 'new-1' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'new-1']);
  });

  it('shows a placeholder for a dossier without organization and venue', async () => {
    const api = fakeApi({ list: jest.fn(() => of({ items: [makeEvent({ organization: null, venueText: null })], total: 1, limit: 200, offset: 0 })) });
    await setup(api);
    expect(await screen.findByText('Ohne Organisation')).toBeInTheDocument();
  });
});
