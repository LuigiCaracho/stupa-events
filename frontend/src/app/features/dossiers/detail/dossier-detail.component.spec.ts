import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { EventsApi } from '../api/events-api.service';
import { fakeApi, fakeAuth, makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import { DossierDetailComponent } from './dossier-detail.component';

const posterBlocker = {
  code: 'image_required',
  field: null,
  severity: 'blocker' as const,
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster' as const,
};
const dateBlocker = { ...posterBlocker, code: 'start_in_past', messageKey: 'guards.start_in_past', fixAction: 'change_date' as const };

describe('DossierDetailComponent', () => {
  async function setup(api = fakeApi(), auth = fakeAuth()) {
    const view = await render(DossierDetailComponent, {
      inputs: { id: 'ev-1' },
      providers: [
        provideRouter([]),
        { provide: EventsApi, useValue: api },
        { provide: AuthService, useValue: auth },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    return { view, api };
  }

  it('shows head, core data and the primary action of the state', async () => {
    const { api } = await setup();
    expect(screen.getByRole('heading', { level: 1, name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByText('Planung')).toBeInTheDocument();
    expect(screen.getByText('Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('Kino')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    expect(api.guards).toHaveBeenCalledWith('ev-1', 'T02');
    expect(await screen.findByText('Alles bereit.')).toBeInTheDocument();
  });

  it('lists the blockers and sends the fix actions to poster and edit form', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [dateBlocker, posterBlocker] }))) });
    await setup(api);
    await userEvent.click(await screen.findByRole('button', { name: 'Datum ändern' }));
    expect(screen.getByLabelText(/Titel/)).toHaveValue('Movienight');
    await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
    expect(screen.queryByLabelText(/Titel/)).not.toBeInTheDocument();
  });

  it('uploads a poster and reloads the dossier', async () => {
    const png = new File(['png'], 'p.png', { type: 'image/png' });
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ reasons: [posterBlocker] }))) });
    const { view } = await setup(api);
    expect(screen.getByText('Noch kein Poster hochgeladen.')).toBeInTheDocument();
    await userEvent.upload(view.container.querySelector('input[type="file"]') as HTMLInputElement, png);
    await userEvent.type(screen.getByLabelText(/Alt-Text/), 'Plakat');
    await userEvent.type(screen.getByLabelText(/Credit/), 'FSI');
    await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Eigenes Werk' }));
    await userEvent.click(screen.getAllByRole('button', { name: 'Poster hochladen' }).at(-1) as HTMLElement);
    expect(api.uploadPoster).toHaveBeenCalledWith('ev-1', png, expect.objectContaining({ altText: 'Plakat', credit: 'FSI', rightsBasis: 'own_work' }));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('shows an existing poster with its scan state and offers to replace it', async () => {
    const poster = { id: 'a1', eventId: 'ev-1', kind: 'poster' as const, displayName: 'p.png', mime: 'image/png', sizeBytes: 3, sha256: 'x', scanStatus: 'pending' as const, altText: 'Plakat Movienight', credit: 'FSI', rightsBasis: 'own_work' as const, derivatives: null, supersedesId: null, createdAt: '2026-10-01T10:00:00Z' };
    await setup(fakeApi({ get: jest.fn(() => of(makeEvent({ poster }))) }));
    expect(screen.getByText('Plakat Movienight', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText(/zählt erst nach dem Scan/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Poster ersetzen' }));
    expect(screen.getByRole('button', { name: 'Poster hochladen' })).toBeInTheDocument();
  });

  it('confirms a transition in the dialog and shows the new state', async () => {
    await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
    expect(await screen.findByRole('dialog', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText('Freigabe', { selector: 'app-status-text' })).toBeInTheDocument();
  });

  it('locks the data in review and hides the edit button', async () => {
    const api = fakeApi({ get: jest.fn(() => of(makeEvent({ state: 'in_review', allowedTransitions: ['T04'] }))) });
    await setup(api);
    expect(screen.getByText(/In der Freigabe gesperrt/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Daten bearbeiten' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Freigeben' })).toBeInTheDocument();
  });

  it('sends only the changed fields with the revision when saving', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Daten bearbeiten' }));
    const title = screen.getByLabelText(/Titel/);
    await userEvent.clear(title);
    await userEvent.type(title, 'Movienight 2');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.patch).toHaveBeenCalledWith('ev-1', { rev: 3, title: 'Movienight 2' });
  });

  it('reloads on a revision conflict', async () => {
    const conflict = new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } });
    const { api } = await setup(fakeApi({ patch: jest.fn(() => throwError(() => conflict)) }));
    await userEvent.click(screen.getByRole('button', { name: 'Daten bearbeiten' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('offers the image exception only with the permission', async () => {
    await setup();
    expect(screen.queryByRole('button', { name: 'Ausnahme ohne Bild' })).not.toBeInTheDocument();
  });

  it('opens the image exception dialog for the editorial role', async () => {
    await setup(fakeApi(), fakeAuth({ can: (p: string) => p === 'event.image_exception' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ausnahme ohne Bild' }));
    expect(await screen.findByRole('dialog', { name: 'Ausnahme ohne Bild' })).toBeInTheDocument();
  });

  it('shows the granted exception', async () => {
    const exception = { grantedBy: 'ed', reason: 'Offenes Präsidium', at: '2026-10-01T10:00:00Z' };
    await setup(fakeApi({ get: jest.fn(() => of(makeEvent({ imageException: exception }))) }), fakeAuth({ can: () => true }));
    expect(screen.getByText('Ausnahme ohne Bild: Offenes Präsidium')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ausnahme ohne Bild' })).not.toBeInTheDocument();
  });

  it('shows the generic not-found text when the dossier cannot be read', async () => {
    await setup(fakeApi({ get: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))) }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Diese Seite gibt es nicht oder du hast keinen Zugriff.');
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('saves every changed field', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Daten bearbeiten' }));
    const type = async (label: RegExp, text: string) => {
      const field = screen.getByLabelText(label);
      await userEvent.clear(field);
      await userEvent.type(field, text);
      await userEvent.tab();
    };
    await type(/Kurztext/, 'Neuer Text');
    await type(/^Ort/, 'Hörsaal 1');
    await type(/Beginn, Datum/, '06.11.2026');
    await type(/Ende, Datum/, '06.11.2026');
    await userEvent.click(screen.getByRole('combobox', { name: /Format oder Kategorie/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Kino' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.patch).toHaveBeenCalledWith('ev-1', {
      rev: 3,
      summary: 'Neuer Text',
      venueText: 'Hörsaal 1',
      startsAt: '2026-11-06T18:00:00Z',
      endsAt: '2026-11-06T21:00:00Z',
    });
  });

  it('refuses an end before the start in the edit form', async () => {
    const { api } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Daten bearbeiten' }));
    const end = screen.getByLabelText(/Ende, Datum/);
    await userEvent.clear(end);
    await userEvent.type(end, '04.11.2026');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.patch).not.toHaveBeenCalled();
    expect(screen.getByText('Ende liegt vor dem Beginn.')).toBeInTheDocument();
  });

  it('reloads after a stale transition and keeps going after a failed upload', async () => {
    const conflict = new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } });
    const tooLarge = new HttpErrorResponse({ status: 413, error: { status: 413, code: 'payload_too_large' } });
    const png = new File(['png'], 'p.png', { type: 'image/png' });
    const api = fakeApi({
      transition: jest.fn(() => throwError(() => conflict)),
      uploadPoster: jest.fn(() => throwError(() => tooLarge)),
    });
    const { view } = await setup(api);
    await userEvent.upload(view.container.querySelector('input[type="file"]') as HTMLInputElement, png);
    await userEvent.type(screen.getByLabelText(/Alt-Text/), 'Plakat');
    await userEvent.type(screen.getByLabelText(/Credit/), 'FSI');
    await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Lizenz' }));
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(api.uploadPoster).toHaveBeenCalled();
    expect(api.get).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('opens the poster upload from the guard list fix button and closes the dialog', async () => {
    const api = fakeApi({
      get: jest.fn(() => of(makeEvent({ poster: { id: 'a', eventId: 'ev-1', kind: 'poster', displayName: 'p', mime: 'image/png', sizeBytes: 1, sha256: 'x', scanStatus: 'infected', altText: 'a', credit: 'c', rightsBasis: 'own_work', derivatives: null, supersedesId: null, createdAt: '2026-10-01T10:00:00Z' } }))),
      guards: jest.fn(() => of(makeGuards({ reasons: [posterBlocker] }))),
    });
    await setup(api);
    expect(screen.getByText(/Scan hat das Poster abgelehnt/)).toBeInTheDocument();
    await userEvent.click(await screen.findByRole('button', { name: 'Poster hochladen' }));
    expect(screen.getByLabelText(/Alt-Text/, { selector: 'input' })).toBeInTheDocument();
  });
});
