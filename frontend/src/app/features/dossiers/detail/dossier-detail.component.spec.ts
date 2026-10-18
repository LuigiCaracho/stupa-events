import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { render, screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, fakeAuth, makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { AUTOSAVE_MS } from '../autosave/draft-autosave';
import { DossierDetailComponent } from './dossier-detail.component';

const posterBlocker = {
  code: 'image_required',
  field: null,
  severity: 'blocker' as const,
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster' as const,
};
const dateBlocker = {
  ...posterBlocker,
  code: 'start_in_past',
  messageKey: 'guards.start_in_past',
  fixAction: 'change_date' as const,
};
const flyerBlocker = {
  ...posterBlocker,
  code: 'flyer_date',
  messageKey: 'guards.flyer_date',
  fixAction: 'confirm_flyer' as const,
};
const conflictError = (current: EventDto) =>
  throwError(
    () => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict', current } }),
  );

const can = (...perms: string[]) => fakeAuth({ can: (p: string) => perms.includes(p) });

async function setup(api = fakeApi(), auth = fakeAuth(), fakeTimers = false) {
  const view = await render(DossierDetailComponent, {
    inputs: { id: 'ev-1' },
    providers: [
      provideRouter([]),
      { provide: EventsApi, useValue: api },
      { provide: AuthService, useValue: auth },
    ],
  });
  view.fixture.detectChanges();
  if (fakeTimers) await jest.advanceTimersByTimeAsync(0);
  else await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toasts = () =>
    TestBed.inject(ToastService)
      .toasts()
      .map((t) => t.message);
  const page = view.fixture.componentInstance as unknown as {
    canLeave(): boolean | Promise<boolean>;
  };
  return { view, api, toasts, page };
}

const indicator = (view: { container: Element }) =>
  within(view.container.querySelector('app-autosave-indicator') as HTMLElement).getByRole('status');

describe('DossierDetailComponent', () => {
  afterEach(() => localStorage.clear());

  it('shows head, form and the primary action of the state', async () => {
    const { api } = await setup();
    expect(screen.getByRole('heading', { level: 1, name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Titel/)).toHaveValue('Movienight');
    expect(screen.getByRole('button', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    expect(api.guards).toHaveBeenCalledWith('ev-1', 'T02');
    expect(await screen.findByText('Alles bereit.')).toBeInTheDocument();
  });

  it('shows rows instead of the form when nothing is editable', async () => {
    await setup(
      fakeApi({
        get: jest.fn(() =>
          of(
            makeEvent({
              state: 'archived',
              editableFields: [],
              lockReason: 'closed',
              allowedTransitions: [],
            }),
          ),
        ),
      }),
    );
    expect(screen.queryByLabelText(/^Titel/)).not.toBeInTheDocument();
    expect(screen.getByText('Dieses Dossier ist abgeschlossen.')).toBeInTheDocument();
  });

  it('shows an error note with a retry when the dossier does not load', async () => {
    const api = fakeApi({
      get: jest
        .fn()
        .mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 404 })))
        .mockReturnValue(of(makeEvent())),
    });
    await setup(api);
    expect(screen.getByRole('alert')).toHaveTextContent('Diese Seite gibt es nicht');
    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
    expect(await screen.findByRole('heading', { name: 'Movienight' })).toBeInTheDocument();
  });

  describe('fix buttons', () => {
    it('sends the fix to the form field or to the poster block', async () => {
      const api = fakeApi({
        guards: jest.fn(() =>
          of(makeGuards({ allowed: false, reasons: [dateBlocker, posterBlocker] })),
        ),
      });
      await setup(api);
      await userEvent.click(await screen.findByRole('button', { name: 'Datum ändern' }));
      await waitFor(() => expect(screen.getByLabelText(/Beginn, Datum/)).toHaveFocus());
      await userEvent.click(screen.getAllByRole('button', { name: 'Poster hochladen' })[0]);
      expect(screen.getByLabelText(/Alt-Text/)).toBeInTheDocument();
    });

    it('confirms the flyer from the guard list', async () => {
      const api = fakeApi({
        guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [flyerBlocker] }))),
      });
      const { toasts } = await setup(api);
      await userEvent.click(await screen.findByRole('button', { name: 'Flyer geprüft' }));
      expect(api.action).toHaveBeenCalledWith('ev-1', 'confirm-flyer', {}, 3);
      expect(toasts()).toContain('Flyer als geprüft markiert.');
    });
  });

  describe('saving', () => {
    it('saves the changed field with the revision and shows the new version', async () => {
      const api = fakeApi({ patch: jest.fn(() => of(makeEvent({ rev: 4, summary: 'Neu' }))) });
      const { toasts } = await setup(api);
      const summary = screen.getByLabelText('Kurztext');
      await userEvent.clear(summary);
      await userEvent.type(summary, 'Neu');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(api.patch).toHaveBeenCalledWith('ev-1', 3, { summary: 'Neu' });
      expect(toasts()).toContain('Gespeichert.');
      expect(await screen.findByText(/Gespeichert \d\d:\d\d/)).toBeInTheDocument();
    });

    it('names the reasons when the server refuses a change in live', async () => {
      const refused = new HttpErrorResponse({
        status: 422,
        error: { status: 422, reasons: [{ ...posterBlocker }] },
      });
      const api = fakeApi({ patch: jest.fn(() => throwError(() => refused)) });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(toasts()[0]).toContain('Nicht möglich: Poster fehlt');
    });

    it('reloads the dossier when the server says a field is locked', async () => {
      const locked = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'field_locked' },
      });
      const api = fakeApi({ patch: jest.fn(() => throwError(() => locked)) });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(toasts()[0]).toBe('Diese Felder sind in der Freigabe gesperrt.');
      expect(api.get).toHaveBeenCalledTimes(2);
    });
  });

  describe('autosave', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => jest.useRealTimers());

    it('sends the draft after 15 seconds and shows the state', async () => {
      const api = fakeApi();
      const { view } = await setup(api, fakeAuth(), true);
      await userEvent
        .setup({ advanceTimers: jest.advanceTimersByTime })
        .type(screen.getByLabelText('Kurztext'), '!');
      expect(indicator(view)).toHaveTextContent('Nicht gespeichert');
      jest.advanceTimersByTime(AUTOSAVE_MS);
      view.fixture.detectChanges();
      expect(api.saveDraft).toHaveBeenCalledWith('ev-1', 3, { summary: 'Film und Popcorn!' });
      view.fixture.detectChanges();
      expect(indicator(view)).toHaveTextContent(/Gespeichert \d\d:\d\d/);
    });

    it('says offline and keeps the text when the draft cannot be sent', async () => {
      const api = fakeApi({
        saveDraft: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 0 }))),
      });
      const { view, toasts } = await setup(api, fakeAuth(), true);
      await userEvent
        .setup({ advanceTimers: jest.advanceTimersByTime })
        .type(screen.getByLabelText('Kurztext'), '!');
      jest.advanceTimersByTime(AUTOSAVE_MS);
      view.fixture.detectChanges();
      expect(indicator(view)).toHaveTextContent('Nicht gespeichert, offline');
      expect(toasts()[0]).toContain('Keine Verbindung. Deine Änderungen sind lokal gespeichert');
      window.dispatchEvent(new Event('online'));
      expect(api.saveDraft).toHaveBeenCalledTimes(2);
    });

    it('opens the edit conflict when the draft meets a newer version', async () => {
      const theirs = makeEvent({ rev: 4, summary: 'Von jemand' });
      const api = fakeApi({
        saveDraft: jest.fn(() => conflictError(theirs)),
        revision: jest.fn(() => of({ rev: 3, snapshot: { summary: 'Film und Popcorn' } })),
      });
      const { view, toasts } = await setup(api, fakeAuth(), true);
      await userEvent
        .setup({ advanceTimers: jest.advanceTimersByTime })
        .type(screen.getByLabelText('Kurztext'), '!');
      jest.advanceTimersByTime(AUTOSAVE_MS);
      view.fixture.detectChanges();
      expect(
        await screen.findByRole('dialog', { name: 'Jemand anderes war schneller' }),
      ).toBeInTheDocument();
      expect(toasts()).toContain('Jemand anderes hat das Dossier geändert.');
      expect(api.revision).toHaveBeenCalledWith('ev-1', 3);
    });
  });

  describe('restoring', () => {
    it('restores a draft of the same revision with a note and lets the person drop it', async () => {
      const api = fakeApi({
        draft: jest.fn(() =>
          of({ baseRev: 3, fields: { summary: 'Entwurf' }, updatedAt: '2026-10-18T12:02:00Z' }),
        ),
      });
      await setup(api);
      expect(screen.getByLabelText('Kurztext')).toHaveValue('Entwurf');
      expect(screen.getByText(/Entwurf von \d\d:\d\d wiederhergestellt\./)).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
      expect(api.discardDraft).toHaveBeenCalledWith('ev-1');
      expect(screen.getByLabelText('Kurztext')).toHaveValue('Film und Popcorn');
      expect(screen.queryByText(/wiederhergestellt/)).not.toBeInTheDocument();
    });

    it('opens the three-way view for a draft of an older revision and merges what the person keeps', async () => {
      const current = makeEvent({ rev: 5, title: 'Movienight' });
      const api = fakeApi({
        get: jest.fn(() => of(current)),
        draft: jest.fn(() =>
          of({ baseRev: 3, fields: { costText: '5 €' }, updatedAt: '2026-10-18T12:02:00Z' }),
        ),
        revision: jest.fn(() => of({ rev: 3, snapshot: { title: 'Movienight' } })),
        patch: jest.fn(() => of(makeEvent({ rev: 6, costText: '5 €' }))),
      });
      await setup(api);
      const dialog = await screen.findByRole('dialog', { name: 'Jemand anderes war schneller' });
      expect(api.revision).toHaveBeenCalledWith('ev-1', 3);
      await userEvent.click(within(dialog).getByRole('button', { name: 'Übernehmen' }));
      expect(api.patch).toHaveBeenCalledWith('ev-1', 5, { costText: '5 €' });
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });

    it('takes the other version when the person reloads', async () => {
      const current = makeEvent({ rev: 5, summary: 'Neu von jemand' });
      const api = fakeApi({
        get: jest.fn(() => of(current)),
        draft: jest.fn(() =>
          of({ baseRev: 3, fields: { summary: 'Meins' }, updatedAt: '2026-10-18T12:02:00Z' }),
        ),
      });
      await setup(api);
      await userEvent.click(
        await screen.findByRole('button', { name: 'Neu laden, meine Änderungen verwerfen' }),
      );
      expect(api.discardDraft).toHaveBeenCalled();
      expect(screen.getByLabelText('Kurztext')).toHaveValue('Neu von jemand');
    });
  });

  describe('transitions and actions', () => {
    it('opens the confirmation for the primary button and applies the result', async () => {
      const api = fakeApi({
        transition: jest.fn(() =>
          of(makeEvent({ state: 'in_review', allowedTransitions: ['T04'], rev: 4 })),
        ),
      });
      await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenCalledWith('ev-1', 'T02', {}, 3);
      expect(await screen.findByRole('button', { name: 'Freigeben' })).toBeInTheDocument();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('saves unsent changes before it opens the confirmation', async () => {
      const api = fakeApi({ patch: jest.fn(() => of(makeEvent({ rev: 4, summary: 'Neu' }))) });
      await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
      expect(api.patch).toHaveBeenCalledWith('ev-1', 3, { summary: 'Film und Popcorn!' });
      expect(await screen.findByRole('dialog', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    });

    it('does not open the confirmation when the save before it fails', async () => {
      const api = fakeApi({
        patch: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
      expect(toasts()[0]).toContain('Das hat nicht geklappt');
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('refreshes when a transition meets a stale dossier and keeps the approved state after a partial publish', async () => {
      const stale = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'conflict' },
      });
      const api = fakeApi({
        transition: jest.fn(() => throwError(() => stale)),
        get: jest.fn(() => of(makeEvent({ rev: 8 }))),
      });
      await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Freigabe anfragen' }));
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(api.get).toHaveBeenCalledTimes(2);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('offers cancel, flyer, exception and assign in the menu for the editorial role', async () => {
      const event = makeEvent({
        state: 'live',
        allowedTransitions: ['T07'],
        allowedActions: [
          'cancel',
          'postpone',
          'confirm-flyer',
          'image-exception',
          'assign-organization',
          'reinstate',
        ],
        publicStatus: 'cancelled',
        editableFields: [],
        lockReason: 'live_critical',
      });
      const api = fakeApi({ get: jest.fn(() => of(event)), action: jest.fn(() => of(event)) });
      const { toasts } = await setup(api, can('event.approve'));
      const open = async (name: string) => {
        await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
        await userEvent.click(screen.getByRole('menuitem', { name }));
      };
      await open('Absagen oder verschieben');
      expect(
        await screen.findByRole('dialog', { name: 'Absagen oder verschieben' }),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
      await open('Ausnahme ohne Bild');
      expect(await screen.findByRole('dialog', { name: 'Ausnahme ohne Bild' })).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
      await open('Organisation zuweisen');
      expect(
        await screen.findByRole('dialog', { name: 'Organisation zuweisen' }),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
      await open('Absage zurücknehmen');
      await userEvent.type(
        await screen.findByLabelText(/Warum nimmst du die Absage zurück/),
        'Termin steht',
      );
      await userEvent.click(screen.getAllByRole('button', { name: 'Absage zurücknehmen' }).at(-1)!);
      expect(api.action).toHaveBeenCalledWith('ev-1', 'reinstate', { reason: 'Termin steht' }, 3);
      await open('Flyer geprüft');
      expect(api.action).toHaveBeenCalledWith('ev-1', 'confirm-flyer', {}, 3);
      expect(toasts()).toContain('Flyer als geprüft markiert.');
    });
  });

  describe('after publishing', () => {
    const live = makeEvent({
      state: 'live',
      publishedRev: 3,
      textReviewedRev: 0,
      rev: 5,
      allowedActions: ['revert-revision', 'acknowledge-changes'],
      editableFields: ['summary'],
      lockReason: 'live_critical',
      allowedTransitions: [],
    });
    const revisions = {
      items: [
        {
          rev: 5,
          at: '2026-10-18T12:02:00Z',
          actor: { sub: 'u2', displayName: 'Anna' },
          actorType: 'human',
          fieldClass: 'text',
          changeNote: null,
          changedFields: ['summary'],
        },
        {
          rev: 4,
          at: '2026-10-18T11:00:00Z',
          actor: { sub: 'u1', displayName: 'Ich' },
          actorType: 'human',
          fieldClass: 'text',
          changeNote: null,
          changedFields: ['summary'],
        },
      ],
      total: 2,
      limit: 20,
      offset: 0,
    };
    const api = () =>
      fakeApi({ get: jest.fn(() => of(live)), revisions: jest.fn(() => of(revisions)) });

    it('shows the change of another person and acknowledges it', async () => {
      const fake = api();
      await setup(fake, can('event.edit_critical_live'));
      expect(
        await screen.findByText(/Seit der Veröffentlichung geändert: Kurztext \(Anna, /),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Gesehen' }));
      expect(fake.action).toHaveBeenCalledWith('ev-1', 'acknowledge-changes', {}, 5);
    });

    it('resets to the published revision after a note', async () => {
      const fake = api();
      await setup(fake, can('event.edit_critical_live'));
      await userEvent.click(await screen.findByRole('button', { name: 'Zurücksetzen' }));
      await userEvent.type(await screen.findByLabelText('Notiz (optional)'), 'Tippfehler');
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Auf diesen Stand zurücksetzen',
        }),
      );
      expect(fake.action).toHaveBeenCalledWith(
        'ev-1',
        'revert-revision',
        { rev: 3, note: 'Tippfehler' },
        5,
      );
    });

    it('resets to an older revision from the history tab', async () => {
      const fake = api();
      await setup(fake, can('event.edit_critical_live'));
      await userEvent.click(screen.getByRole('tab', { name: 'Verlauf' }));
      const buttons = await screen.findAllByRole('button', {
        name: 'Auf diesen Stand zurücksetzen',
      });
      await userEvent.click(buttons[0]);
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', {
          name: 'Auf diesen Stand zurücksetzen',
        }),
      );
      expect(fake.action).toHaveBeenCalledWith('ev-1', 'revert-revision', { rev: 4 }, 5);
    });

    it('shows no banner for a person without the right', async () => {
      await setup(api(), can());
      expect(screen.queryByText(/Seit der Veröffentlichung geändert/)).not.toBeInTheDocument();
    });
  });

  describe('poster', () => {
    it('uploads a poster and refreshes the dossier', async () => {
      const png = new File(['png'], 'p.png', { type: 'image/png' });
      const api = fakeApi();
      const { toasts, view } = await setup(api);
      expect(screen.getByText('Noch kein Poster hochgeladen.')).toBeInTheDocument();
      await userEvent.upload(
        view.container.querySelector('input[type="file"]') as HTMLInputElement,
        png,
      );
      await userEvent.type(screen.getByLabelText(/Alt-Text/), 'Plakat');
      await userEvent.type(screen.getByLabelText(/Credit/), 'Mara');
      await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
      await userEvent.click(screen.getByRole('option', { name: 'Eigenes Werk' }));
      await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
      expect(api.uploadPoster).toHaveBeenCalledWith(
        'ev-1',
        png,
        expect.objectContaining({ altText: 'Plakat', personsDepicted: false }),
      );
      expect(toasts()).toContain('Poster hochgeladen.');
      expect(api.get).toHaveBeenCalledTimes(2);
    });

    it('shows an existing poster with its scan state and offers to replace it', async () => {
      const poster = {
        id: 'p1',
        eventId: 'ev-1',
        kind: 'poster' as const,
        displayName: 'p.png',
        mime: 'image/png',
        sizeBytes: 3,
        sha256: 'x',
        scanStatus: 'pending' as const,
        altText: 'Plakat',
        credit: 'Mara',
        rightsBasis: 'own_work' as const,
        derivatives: null,
        supersedesId: null,
        createdAt: '2026-10-01T10:00:00Z',
      };
      await setup(fakeApi({ get: jest.fn(() => of(makeEvent({ poster }))) }));
      expect(
        screen.getByText('Wird geprüft, das Poster zählt erst nach dem Scan.'),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Poster ersetzen' }));
      expect(screen.getByRole('button', { name: 'Poster hochladen' })).toBeInTheDocument();
    });

    it('shows a rejected scan as an error and reports a failed upload', async () => {
      const poster = {
        id: 'p1',
        altText: 'Plakat',
        credit: 'Mara',
        scanStatus: 'infected',
      } as never;
      const api = fakeApi({
        get: jest.fn(() => of(makeEvent({ poster }))),
        uploadPoster: jest.fn(() =>
          throwError(
            () =>
              new HttpErrorResponse({
                status: 413,
                error: { status: 413, code: 'payload_too_large' },
              }),
          ),
        ),
      });
      const { toasts, view } = await setup(api);
      expect(
        screen.getByText('Der Scan hat das Poster abgelehnt. Bitte lade ein anderes hoch.'),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Poster ersetzen' }));
      await userEvent.upload(
        view.container.querySelector('input[type="file"]') as HTMLInputElement,
        new File(['x'], 'p.png', { type: 'image/png' }),
      );
      await userEvent.type(screen.getByLabelText(/Alt-Text/), 'Plakat');
      await userEvent.type(screen.getByLabelText(/Credit/), 'Mara');
      await userEvent.click(screen.getByRole('combobox', { name: /Rechtegrundlage/ }));
      await userEvent.click(screen.getByRole('option', { name: 'Eigenes Werk' }));
      await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
      expect(toasts()[0]).toContain('10 MiB');
    });
  });

  describe('leaving', () => {
    it('lets the person go when nothing is unsent', async () => {
      const { page } = await setup();
      expect(page.canLeave()).toBe(true);
    });

    async function dirty(api = fakeApi()) {
      const ctx = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      const answer = ctx.page.canLeave() as Promise<boolean>;
      await screen.findByRole('dialog', { name: 'Ungespeicherte Änderungen' });
      return { ...ctx, answer };
    }

    it('stays when the person chooses Bleiben', async () => {
      const { answer } = await dirty();
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Bleiben' }),
      );
      await expect(answer).resolves.toBe(false);
    });

    it('goes after Verwerfen and drops the draft', async () => {
      const { answer, api } = await dirty();
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Verwerfen' }),
      );
      await expect(answer).resolves.toBe(true);
      expect(api.discardDraft).toHaveBeenCalled();
    });

    it('goes after Speichern', async () => {
      const { answer, api } = await dirty();
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Speichern' }),
      );
      await expect(answer).resolves.toBe(true);
      expect(api.patch).toHaveBeenCalled();
    });

    it('stays when the save fails', async () => {
      const { answer } = await dirty(
        fakeApi({ patch: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
      );
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Speichern' }),
      );
      await expect(answer).resolves.toBe(false);
    });

    it('warns before the tab closes only while changes are unsent', async () => {
      await setup();
      const clean = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(clean);
      expect(clean.defaultPrevented).toBe(false);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      const unsent = new Event('beforeunload', { cancelable: true });
      window.dispatchEvent(unsent);
      expect(unsent.defaultPrevented).toBe(true);
    });
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByText('Alles bereit.');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  describe('edge cases', () => {
    it('still renders when the lookups and the revisions fail', async () => {
      const down = () => throwError(() => new HttpErrorResponse({ status: 500 }));
      const live = makeEvent({
        state: 'live',
        editableFields: ['summary'],
        lockReason: 'live_critical',
        allowedTransitions: [],
      });
      const api = fakeApi({
        get: jest.fn(() => of(live)),
        categories: jest.fn(down),
        venues: jest.fn(down),
        revisions: jest.fn(down),
      });
      await setup(api, can('event.edit_critical_live'));
      expect(screen.getByLabelText('Kurztext')).toBeEnabled();
      expect(screen.queryByText(/Seit der Veröffentlichung geändert/)).not.toBeInTheDocument();
    });

    it('offers the image exception from the permission when the server lists no actions', async () => {
      const event = makeEvent({ allowedActions: undefined });
      await setup(fakeApi({ get: jest.fn(() => of(event)) }), can('event.image_exception'));
      await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
      expect(screen.getByRole('menuitem', { name: 'Ausnahme ohne Bild' })).toBeInTheDocument();
    });

    it('offers nothing when the exception is already granted', async () => {
      const event = makeEvent({
        imageException: { grantedBy: 'e', reason: 'x', at: '2026-10-01T10:00:00Z' },
        allowedTransitions: [],
      });
      await setup(fakeApi({ get: jest.fn(() => of(event)) }), can('event.image_exception'));
      expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument();
    });

    it('sends the rights fix to the poster block and focuses the end for "Ende setzen"', async () => {
      const rights = {
        ...posterBlocker,
        code: 'rights_incomplete',
        messageKey: 'guards.rights_incomplete',
        fixAction: 'fill_rights' as const,
      };
      const setEnd = {
        ...posterBlocker,
        code: 'end_estimated',
        severity: 'warning' as const,
        messageKey: 'guards.end_estimated',
        fixAction: 'set_end' as const,
      };
      const api = fakeApi({
        guards: jest.fn(() => of(makeGuards({ allowed: true, reasons: [rights, setEnd] }))),
      });
      await setup(api);
      await userEvent.click(await screen.findByRole('button', { name: 'Ende setzen' }));
      await waitFor(() => expect(screen.getByLabelText(/Ende, Datum/)).toHaveFocus());
      await userEvent.click(screen.getByRole('button', { name: 'Rechte ergänzen' }));
      expect(screen.getByLabelText(/Alt-Text/)).toBeInTheDocument();
    });

    it('falls back to a reload when the refresh after a stale card fails', async () => {
      const stale = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'field_locked' },
      });
      const api = fakeApi({
        patch: jest.fn(() => throwError(() => stale)),
        get: jest
          .fn()
          .mockReturnValueOnce(of(makeEvent()))
          .mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 500 })))
          .mockReturnValue(of(makeEvent())),
      });
      await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      await waitFor(() => expect(api.get).toHaveBeenCalledTimes(3));
    });

    it('loads the current version itself when the conflict carries none and survives a missing base', async () => {
      const conflict = throwError(
        () => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } }),
      );
      const api = fakeApi({
        patch: jest.fn(() => conflict),
        get: jest
          .fn()
          .mockReturnValueOnce(of(makeEvent()))
          .mockReturnValue(of(makeEvent({ rev: 4, summary: 'Neu' }))),
        revision: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))),
      });
      await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(
        await screen.findByRole('dialog', { name: 'Jemand anderes war schneller' }),
      ).toBeInTheDocument();
      expect(screen.getAllByText('–').length).toBeGreaterThan(0);
    });

    it('reports a failure of the merge after a conflict', async () => {
      const current = makeEvent({ rev: 5 });
      const api = fakeApi({
        get: jest.fn(() => of(current)),
        draft: jest.fn(() =>
          of({ baseRev: 3, fields: { costText: '5 €' }, updatedAt: '2026-10-18T12:02:00Z' }),
        ),
        patch: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      });
      const { toasts } = await setup(api);
      await userEvent.click(await screen.findByRole('button', { name: 'Übernehmen' }));
      expect(toasts().at(-1)).toContain('Das hat nicht geklappt');
    });

    it('applies the draft by itself after 30 minutes in planning and reports a failure', async () => {
      jest.useFakeTimers();
      try {
        const api = fakeApi({
          patch: jest
            .fn()
            .mockReturnValueOnce(of(makeEvent({ rev: 4, summary: 'Neu' })))
            .mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 }))),
        });
        const { view, toasts } = await setup(api, fakeAuth(), true);
        await userEvent
          .setup({ advanceTimers: jest.advanceTimersByTime })
          .type(screen.getByLabelText('Kurztext'), '!');
        jest.advanceTimersByTime(30 * 60_000);
        view.fixture.detectChanges();
        expect(api.patch).toHaveBeenCalledTimes(1);
        await userEvent
          .setup({ advanceTimers: jest.advanceTimersByTime })
          .type(screen.getByLabelText('Kurztext'), '?');
        jest.advanceTimersByTime(30 * 60_000);
        expect(toasts().at(-1)).toContain('Das hat nicht geklappt');
      } finally {
        jest.useRealTimers();
      }
    });

    it('restores the text that was kept offline and sends it', async () => {
      jest.useFakeTimers();
      try {
        localStorage.setItem(
          'draft:ev-1:u1',
          JSON.stringify({
            baseRev: 3,
            fields: { summary: 'Offline' },
            at: '2099-01-01T10:00:00Z',
          }),
        );
        const api = fakeApi();
        await setup(api, fakeAuth(), true);
        expect(screen.getByLabelText('Kurztext')).toHaveValue('Offline');
        jest.advanceTimersByTime(AUTOSAVE_MS);
        expect(api.saveDraft).toHaveBeenCalledWith('ev-1', 3, { summary: 'Offline' });
      } finally {
        jest.useRealTimers();
      }
    });
  });
});
