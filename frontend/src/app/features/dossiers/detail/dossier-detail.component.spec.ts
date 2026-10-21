/** The dossier page (M5b): head and action bar, poster slot, hints, anchor navigation, the sections and the dialogs. */
import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import type { Attachment, EventAction, EventDto } from '../api/event.models';
import { DossierCommands } from '../api/dossier-commands';
import { can, setup } from '../../../../testing/dossier-detail-harness';

const poster = (over: Partial<Attachment> = {}): Attachment => ({
  id: 'p1',
  eventId: 'ev-1',
  kind: 'poster',
  displayName: 'p.png',
  mime: 'image/png',
  sizeBytes: 3,
  sha256: 'x',
  scanStatus: 'clean',
  altText: 'Plakat',
  credit: 'Mara',
  rightsBasis: 'own_work',
  derivatives: {
    thumb400: { id: 'd1', width: 400, height: 300 },
    card1200: { id: 'd2', width: 1200, height: 900 },
    og1200x630: { id: 'd3', width: 1200, height: 630 },
  },
  supersedesId: null,
  createdAt: '2026-10-01T10:00:00Z',
  ...over,
});

const published = (over: Partial<EventDto> = {}): EventDto =>
  makeEvent({
    state: 'published',
    allowedActions: ['unpublish', 'archive', 'cancel', 'postpone', 'clone'],
    ...over,
  });

const apiWith = (event: EventDto, extra: Record<string, unknown> = {}) =>
  fakeApi({ get: jest.fn(() => of(event)), ...extra });

const withHints = (...items: { code: string; severity: 'info' | 'warn'; field: string | null }[]) =>
  jest.fn(() => of({ items }));

describe('DossierDetailComponent', () => {
  afterEach(() => localStorage.clear());

  describe('structure', () => {
    it('shows head, poster slot, the anchor navigation and the sections in order', async () => {
      const { view } = await setup();
      expect(screen.getByRole('heading', { level: 1, name: 'Movienight' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Bild' })).toBeInTheDocument();
      const nav = screen.getByRole('navigation', { name: 'Abschnitte des Dossiers' });
      expect(within(nav).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual([
        '#eckdaten',
        '#doku',
        '#anhaenge',
        '#checkliste',
        '#mails',
        '#angebote',
        '#so-lief-es',
        '#verlauf',
      ]);
      const ids = Array.from(view.container.querySelectorAll('.dd__sec')).map((s) => s.id);
      expect(ids).toEqual([
        'eckdaten',
        'doku',
        'anhaenge',
        'checkliste',
        'mails',
        'angebote',
        'so-lief-es',
        'verlauf',
      ]);
    });

    it('shows the counters in the anchor navigation', async () => {
      await setup();
      const nav = screen.getByRole('navigation', { name: 'Abschnitte des Dossiers' });
      expect(within(nav).getByRole('link', { name: /Anhänge/ })).toHaveTextContent('2');
      expect(within(nav).getByRole('link', { name: /Checkliste/ })).toHaveTextContent('3');
      expect(within(nav).getByRole('link', { name: /Verlauf/ })).toHaveTextContent('4');
    });

    it('moves the focus to the section a link names, by mouse and by keyboard', async () => {
      await setup();
      const nav = screen.getByRole('navigation', { name: 'Abschnitte des Dossiers' });
      await userEvent.click(within(nav).getByRole('link', { name: /Checkliste/ }));
      expect(document.getElementById('checkliste')).toHaveFocus();
      expect(within(nav).getByRole('link', { name: /Checkliste/ })).toHaveAttribute(
        'aria-current',
        'location',
      );
      within(nav).getByRole('link', { name: /Mails/ }).focus();
      await userEvent.keyboard('{Enter}');
      expect(document.getElementById('mails')).toHaveFocus();
    });

    it.each([
      ['Anleitung', 'Noch keine Anleitung.'],
      ['Anhänge', 'Anhang hinzufügen'],
      ['Checkliste', 'Vorlage anwenden'],
      ['Mails', 'Neue Vorlage'],
      ['So lief es', 'Ergebnis speichern'],
    ])('has the section %s with its content on the one page', async (heading, content) => {
      await setup();
      expect(screen.getAllByRole('heading', { name: heading }).length).toBeGreaterThan(0);
      expect(screen.getAllByText(content).length).toBeGreaterThan(0);
    });

    it('offers a question on the poster and the fields inside the Verlauf', async () => {
      await setup();
      expect(screen.getByRole('heading', { name: 'Rückfrage zu einer Angabe' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Rückfrage zu Poster' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: 'Rückfragen' })).toBeInTheDocument();
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

    it('has no axe violations', async () => {
      const { view } = await setup();
      expect(await runAxe(view.container)).toHaveNoViolations();
    });
  });

  describe('Eckdaten', () => {
    it('are open with the form for a draft', async () => {
      await setup();
      expect(screen.getByRole('button', { name: 'Eckdaten' })).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByLabelText(/^Titel/)).toBeVisible();
    });

    it('are closed for a published event, and open with the toggle', async () => {
      await setup(apiWith(published({ editableFields: ['summary'] })));
      const toggle = screen.getByRole('button', { name: 'Eckdaten' });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      expect(screen.getByLabelText('Kurztext')).not.toBeVisible();
      await userEvent.click(toggle);
      expect(screen.getByLabelText('Kurztext')).toBeVisible();
    });

    it('show rows and the reason instead of the form in the archive', async () => {
      await setup(
        apiWith(makeEvent({ state: 'archived', editableFields: [], allowedActions: ['clone'] })),
      );
      expect(screen.queryByLabelText(/^Titel/)).not.toBeInTheDocument();
      expect(screen.getByText(/Im Archiv lassen sich die Eckdaten nicht mehr ändern/)).toBeInTheDocument();
    });

    it('keep the documents of an archived dossier writable', async () => {
      await setup(
        apiWith(makeEvent({ state: 'archived', editableFields: [], allowedActions: [] })),
        can('event.edit'),
      );
      expect(screen.getByRole('button', { name: 'Anhang hinzufügen' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Ergebnis speichern' })).toBeInTheDocument();
    });

    it('say how many due dates a date change recomputed', async () => {
      const api = fakeApi({
        patch: jest.fn(() => of(makeEvent({ rev: 4, summary: 'Neu', checklistRecomputed: 2 }))),
      });
      await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(await screen.findByText('2 Fälligkeiten neu berechnet.')).toBeInTheDocument();
    });

    it('put the budget suggestion into the facts of the dossier', async () => {
      const { page, toasts, http } = await setup();
      page.useBudget(123456);
      const req = http.expectOne('/api/events/ev-1/facts');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ budgetCents: 123456 });
      expect(req.request.headers.get('If-Match')).toBe('"3"');
      req.flush(makeEvent({ rev: 4, facts: { budgetCents: 123456 } }));
      expect(toasts()).toContain('Rahmen gespeichert.');
    });
  });

  describe('hints', () => {
    it('shows the banner "Ohne Bild nicht bewerbbar" for a published event without a poster', async () => {
      await setup(apiWith(published(), { hints: withHints({ code: 'no_poster', severity: 'warn', field: null }) }));
      expect(screen.getByText(/Ohne Bild nicht bewerbbar\. Auf der öffentlichen Seite/)).toBeInTheDocument();
      expect(screen.getByText('Fehlt noch (1)')).toBeInTheDocument();
    });

    it('shows no banner for a draft without a poster, and no banner with a poster', async () => {
      await setup();
      expect(screen.queryByText(/Auf der öffentlichen Seite erscheint ein Platzhalter/)).not.toBeInTheDocument();
      TestBed.resetTestingModule();
      await setup(apiWith(published({ poster: poster() })));
      expect(screen.queryByText(/Auf der öffentlichen Seite erscheint ein Platzhalter/)).not.toBeInTheDocument();
    });

    it('lists the hints as plain text, the important ones first, and never blocks', async () => {
      await setup(
        apiWith(makeEvent(), {
          hints: withHints(
            { code: 'no_summary', severity: 'info', field: 'summary' },
            { code: 'poster_consent_missing', severity: 'warn', field: null },
          ),
        }),
      );
      await userEvent.click(screen.getByText('Fehlt noch (2)'));
      const items = screen.getAllByRole('listitem').filter((li) => li.classList.contains('hl__item'));
      expect(items[0]).toHaveTextContent('Wichtig');
      expect(items[0]).toHaveTextContent('Einwilligung fehlt');
      expect(items[1]).toHaveTextContent('Tipp');
      expect(items[1]).toHaveTextContent('Es fehlt ein Kurztext.');
    });

    it('sends a hint to the field, opening the closed Eckdaten', async () => {
      await setup(
        apiWith(published({ editableFields: ['summary', 'primaryCategoryId'], poster: poster() }), {
          hints: withHints({ code: 'no_summary', severity: 'info', field: 'summary' }),
        }),
      );
      await userEvent.click(screen.getByText('Fehlt noch (1)'));
      await userEvent.click(screen.getByRole('button', { name: 'Ergänzen' }));
      await waitFor(() => expect(screen.getByLabelText('Kurztext')).toHaveFocus());
      expect(screen.getByRole('button', { name: 'Eckdaten' })).toHaveAttribute('aria-expanded', 'true');
    });

    it('sends a poster hint to the poster slot and an open outcome to "So lief es"', async () => {
      await setup(
        apiWith(published(), {
          hints: withHints(
            { code: 'no_poster', severity: 'warn', field: null },
            { code: 'outcome_open', severity: 'info', field: null },
          ),
        }),
      );
      await userEvent.click(screen.getByText('Fehlt noch (2)'));
      const fix = screen.getAllByRole('button', { name: 'Ergänzen' });
      await userEvent.click(fix[0]);
      expect(screen.getByRole('heading', { name: 'Bild' })).toHaveFocus();
      await userEvent.click(fix[1]);
      expect(document.getElementById('so-lief-es')).toHaveFocus();
    });

    it('opens the location dialog for an unconfirmed free place', async () => {
      await setup(
        apiWith(published({ allowedActions: ['confirm-location'] }), {
          hints: withHints({ code: 'location_unconfirmed', severity: 'warn', field: 'venueText' }),
        }),
      );
      await userEvent.click(screen.getByText('Fehlt noch (1)'));
      await userEvent.click(screen.getByRole('button', { name: 'Ergänzen' }));
      expect(await screen.findByRole('dialog', { name: 'Ort ist öffentlich?' })).toBeInTheDocument();
    });

    it('reloads the hints after the dossier changed', async () => {
      const api = apiWith(makeEvent(), {
        publish: jest.fn(() => of(published({ rev: 4, allowedActions: [] }))),
      });
      await setup(api);
      expect(api.hints).toHaveBeenCalledTimes(1);
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      await waitFor(() => expect(api.hints).toHaveBeenCalledTimes(2));
    });
  });

  describe('actions', () => {
    it('publishes with the revision, shows the new state and tells so', async () => {
      const api = fakeApi({
        publish: jest.fn(() => of(published({ rev: 4, allowedActions: ['unpublish'] }))),
      });
      const { toasts } = await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      expect(api.publish).toHaveBeenCalledWith('ev-1', 3);
      expect(await screen.findByRole('button', { name: 'Zurückziehen' })).toBeInTheDocument();
      expect(screen.getByText('Veröffentlicht', { selector: 'app-status-text' })).toBeInTheDocument();
      expect(toasts()).toContain('Veröffentlicht.');
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('saves unsent changes before it publishes and publishes the saved revision', async () => {
      const api = fakeApi({ patch: jest.fn(() => of(makeEvent({ rev: 4, summary: 'Neu' }))) });
      await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      expect(api.patch).toHaveBeenCalledWith('ev-1', 3, { summary: 'Film und Popcorn!' });
      await waitFor(() => expect(api.publish).toHaveBeenCalledWith('ev-1', 4));
    });

    it('does not publish when the save before it fails', async () => {
      const api = fakeApi({
        patch: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      expect(toasts()[0]).toContain('Das hat nicht geklappt');
      expect(api.publish).not.toHaveBeenCalled();
    });

    it('names the missing fields when the server refuses the publication', async () => {
      const refused = new HttpErrorResponse({
        status: 422,
        error: {
          status: 422,
          code: 'publish_incomplete',
          reasons: [
            { code: 'field_missing', field: 'title' },
            { code: 'field_missing', field: 'organization_id' },
          ],
        },
      });
      const api = fakeApi({ publish: jest.fn(() => throwError(() => refused)) });
      const { toasts } = await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      expect(toasts()[0]).toBe('Zum Veröffentlichen fehlt noch: Titel, Organisation.');
    });

    it('refreshes when the dossier changed meanwhile', async () => {
      const stale = new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } });
      const api = fakeApi({
        publish: jest.fn(() => throwError(() => stale)),
        get: jest.fn(() => of(makeEvent({ rev: 8 }))),
      });
      const { toasts } = await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Veröffentlichen' }));
      expect(toasts()[0]).toBe('Jemand anderes hat das inzwischen geändert. Bitte lade neu.');
      expect(api.get).toHaveBeenCalledTimes(2);
    });

    it.each([
      ['unpublish', 'Zurückziehen', 'Zurückgezogen. Das Event ist nicht mehr öffentlich.'],
      ['archive', 'Archivieren', 'Archiviert.'],
      ['restore', 'Wiederherstellen', 'Wiederhergestellt als Entwurf.'],
    ] as const)('runs %s from its button and tells so', async (call, label, message) => {
      const actions: EventAction[] = [call];
      const api = apiWith(makeEvent({ state: 'published', allowedActions: actions }));
      const { toasts } = await setup(api);
      await userEvent.click(screen.getByRole('button', { name: label }));
      expect(api[call]).toHaveBeenCalledWith('ev-1', 3);
      expect(toasts()).toContain(message);
    });

    it('opens "Neu aus Vorlage" for the dossier', async () => {
      const { navigate } = await setup(apiWith(makeEvent({ allowedActions: ['clone'] })));
      await userEvent.click(screen.getByRole('button', { name: 'Neu aus diesem Event' }));
      expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], { queryParams: { vorlage: 'ev-1' } });
    });

    it('cancels through the small dialog and shows the mark', async () => {
      const cancelled = published({ publicStatus: 'cancelled', allowedActions: ['reinstate'] });
      const api = apiWith(published(), { cancel: jest.fn(() => of(cancelled)) });
      await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Absagen' }));
      expect(await screen.findByRole('dialog', { name: 'Event absagen' })).toBeInTheDocument();
      await userEvent.click(screen.getAllByRole('button', { name: 'Absagen' }).at(-1)!);
      expect(api.cancel).toHaveBeenCalledWith('ev-1', 3, { publicReasonCode: 'none' });
      expect(await screen.findByRole('button', { name: 'Wieder ansetzen' })).toBeInTheDocument();
      expect(screen.getAllByText('Abgesagt').length).toBeGreaterThan(0);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('postpones and puts the event back on through the same dialog', async () => {
      const api = apiWith(published({ allowedActions: ['postpone', 'reinstate'] }));
      await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Verschieben' }));
      expect(await screen.findByRole('dialog', { name: 'Event verschieben' })).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
      await userEvent.click(screen.getByRole('button', { name: 'Wieder ansetzen' }));
      expect(await screen.findByRole('dialog', { name: 'Event wieder ansetzen' })).toBeInTheDocument();
      await userEvent.click(screen.getAllByRole('button', { name: 'Wieder ansetzen' }).at(-1)!);
      expect(api.reinstate).toHaveBeenCalledWith('ev-1', 3, {});
    });

    it('opens the location dialog from the menu', async () => {
      await setup(apiWith(published({ allowedActions: ['confirm-location'] })));
      await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
      await userEvent.click(screen.getByRole('menuitem', { name: 'Ort bestätigen' }));
      expect(await screen.findByRole('dialog', { name: 'Ort ist öffentlich?' })).toBeInTheDocument();
    });

    it('opens "Als Format speichern" from the menu, with the title as the suggestion', async () => {
      await setup(apiWith(published({ allowedActions: ['save-as-format'] })));
      await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
      await userEvent.click(screen.getByRole('menuitem', { name: 'Als Format speichern' }));
      const dialog = await screen.findByRole('dialog', { name: 'Als Format speichern' });
      expect(await within(dialog).findByDisplayValue('Movienight')).toBeInTheDocument();
    });

    it('answers the palette command only when the dossier allows it', async () => {
      await setup(apiWith(published({ allowedActions: ['save-as-format'] })));
      TestBed.inject(DossierCommands).send('save-as-format');
      expect(await screen.findByRole('dialog', { name: 'Als Format speichern' })).toBeInTheDocument();
      expect(TestBed.inject(DossierCommands).pending()).toBeNull();
      expect(TestBed.inject(DossierCommands).allowed()).toEqual(['save-as-format']);
    });

    it('ignores the palette command when the action is not allowed', async () => {
      await setup(apiWith(published({ allowedActions: [] })));
      TestBed.inject(DossierCommands).send('save-as-format');
      await new Promise((r) => setTimeout(r));
      expect(screen.queryByRole('dialog', { name: 'Als Format speichern' })).not.toBeInTheDocument();
      expect(TestBed.inject(DossierCommands).pending()).toBeNull();
    });
  });

  describe('poster slot', () => {
    it('says "Ohne Bild nicht bewerbbar" with the upload in the empty slot', async () => {
      await setup();
      const slot = screen.getByRole('heading', { name: 'Bild' }).closest('section') as HTMLElement;
      expect(within(slot).getByText('Ohne Bild nicht bewerbbar')).toBeInTheDocument();
      expect(within(slot).getByRole('button', { name: 'Bild hochladen' })).toBeInTheDocument();
    });

    it('uploads with the file alone and refreshes the dossier', async () => {
      const png = new File(['png'], 'p.png', { type: 'image/png' });
      const api = fakeApi();
      const { toasts, view } = await setup(api);
      await userEvent.upload(
        view.container.querySelector('input[type="file"]') as HTMLInputElement,
        png,
      );
      await userEvent.click(screen.getByRole('button', { name: 'Bild hochladen' }));
      expect(api.uploadPoster).toHaveBeenCalledWith(
        'ev-1',
        png,
        expect.objectContaining({ rightsBasis: 'unknown', personsDepicted: false }),
      );
      expect(toasts()).toContain('Bild hochgeladen.');
      expect(api.get).toHaveBeenCalledTimes(2);
    });

    it('shows the picture large with its scan state and offers to replace or remove it', async () => {
      const { view } = await setup(
        apiWith(makeEvent({ poster: poster({ scanStatus: 'pending' }) })),
      );
      const img = view.container.querySelector('img.ps__img') as HTMLImageElement;
      expect(img.getAttribute('src')).toBe('/api/events/ev-1/poster/file?variant=thumb400');
      expect(img).toHaveAttribute('alt', 'Plakat');
      expect(screen.getByText('Wird geprüft, das Bild erscheint erst nach dem Scan.')).toBeInTheDocument();
      expect(screen.queryByText('Ohne Bild nicht bewerbbar')).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Bild ersetzen' }));
      expect(screen.getByRole('button', { name: 'Bild hochladen' })).toBeInTheDocument();
    });

    it('removes the picture and refreshes', async () => {
      const api = apiWith(makeEvent({ poster: poster() }));
      const { toasts } = await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Bild entfernen' }));
      expect(toasts()).toContain('Bild entfernt.');
      expect(api.get).toHaveBeenCalledTimes(2);
    });

    it('shows a rejected scan as an error and reports a failed upload', async () => {
      const api = apiWith(makeEvent({ poster: poster({ scanStatus: 'infected' }) }), {
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
        screen.getByText('Der Scan hat das Bild abgelehnt. Bitte lade ein anderes hoch.'),
      ).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Bild ersetzen' }));
      await userEvent.upload(
        view.container.querySelector('input[type="file"]') as HTMLInputElement,
        new File(['x'], 'p.png', { type: 'image/png' }),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Bild hochladen' }));
      expect(toasts()[0]).toContain('10 MiB');
    });

    it('offers no upload and no removal in the archive', async () => {
      await setup(
        apiWith(makeEvent({ state: 'archived', editableFields: [], poster: poster(), allowedActions: [] })),
      );
      expect(screen.queryByRole('button', { name: 'Bild ersetzen' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Bild entfernen' })).not.toBeInTheDocument();
    });
  });

  describe('history', () => {
    it('resets to an older revision after a note', async () => {
      const event = published({ rev: 5, allowedActions: ['revert-revision'], editableFields: ['summary'] });
      const api = apiWith(event, {
        revisions: jest.fn(() =>
          of({
            items: [
              { rev: 5, at: '2026-10-18T12:00:00Z', actor: { sub: 'u', displayName: 'Anna' }, actorType: 'human', changeNote: null, changedFields: ['summary'] },
              { rev: 4, at: '2026-10-18T11:00:00Z', actor: { sub: 'u', displayName: 'Anna' }, actorType: 'human', changeNote: null, changedFields: ['summary'] },
            ],
            total: 2,
            limit: 100,
            offset: 0,
          }),
        ),
      });
      const { toasts } = await setup(api);
      await userEvent.click((await screen.findAllByRole('button', { name: 'Auf diesen Stand zurücksetzen' }))[0]);
      const dialog = await screen.findByRole('dialog', { name: 'Auf diesen Stand zurücksetzen' });
      await userEvent.type(within(dialog).getByLabelText(/Notiz/), 'Tippfehler');
      await userEvent.click(within(dialog).getByRole('button', { name: 'Auf diesen Stand zurücksetzen' }));
      expect(api.revert).toHaveBeenCalledWith('ev-1', 5, { rev: 4, note: 'Tippfehler' });
      expect(toasts()).toContain('Zurückgesetzt.');
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });
  });

  describe('rights', () => {
    it('shows a reader no actions and no write controls', async () => {
      await setup(
        apiWith(published({ allowedActions: [], editableFields: [] })),
        fakeAuth({ can: () => false }),
      );
      expect(screen.queryByRole('group', { name: 'Aktionen' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Anhang hinzufügen' })).not.toBeInTheDocument();
    });
  });
});
