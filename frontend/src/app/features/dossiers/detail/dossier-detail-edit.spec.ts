/** Editing on the dossier page: save, autosave, restore of a draft, the edit conflict and the question on leaving. */
import { HttpErrorResponse } from '@angular/common/http';
import { screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import type { EventDto } from '../api/event.models';
import { AUTOSAVE_MS } from '../autosave/draft-autosave';
import { indicator, setup } from '../../../../testing/dossier-detail-harness';

const conflictError = (current: EventDto) =>
  throwError(
    () => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict', current } }),
  );

describe('DossierDetailComponent editing', () => {
  afterEach(() => localStorage.clear());

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

    it('keeps the opened Eckdaten of a published event open after the save', async () => {
      const published = (rev: number, summary?: string) =>
        makeEvent({ state: 'published', rev, summary, editableFields: ['summary'] });
      const api = fakeApi({
        get: jest.fn(() => of(published(3))),
        patch: jest.fn(() => of(published(4, 'Neu'))),
      });
      await setup(api);
      await userEvent.click(screen.getByRole('button', { name: 'Eckdaten' }));
      await userEvent.type(screen.getByLabelText('Kurztext'), 'Neu');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(await screen.findByText(/Gespeichert \d\d:\d\d/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Eckdaten' })).toHaveAttribute('aria-expanded', 'true');
    });

    it('asks to check the input when the server refuses a save', async () => {
      const refused = new HttpErrorResponse({
        status: 422,
        error: { status: 422, code: 'validation_error' },
      });
      const api = fakeApi({ patch: jest.fn(() => throwError(() => refused)) });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(toasts()[0]).toBe('Bitte prüfe deine Eingaben.');
    });

    it('reloads the dossier when the state does not allow the change', async () => {
      const locked = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'invalid_state' },
      });
      const api = fakeApi({ patch: jest.fn(() => throwError(() => locked)) });
      const { toasts } = await setup(api);
      await userEvent.type(screen.getByLabelText('Kurztext'), '!');
      await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
      expect(toasts()[0]).toBe('Das ist im aktuellen Zustand nicht möglich.');
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

    it('applies the draft by itself after 30 minutes in a draft dossier and reports a failure', async () => {
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
    });

    it('restores the text that was kept offline and sends it', async () => {
      localStorage.setItem(
        'draft:ev-1:u1',
        JSON.stringify({ baseRev: 3, fields: { summary: 'Offline' }, at: '2099-01-01T10:00:00Z' }),
      );
      const api = fakeApi();
      await setup(api, fakeAuth(), true);
      expect(screen.getByLabelText('Kurztext')).toHaveValue('Offline');
      jest.advanceTimersByTime(AUTOSAVE_MS);
      expect(api.saveDraft).toHaveBeenCalledWith('ev-1', 3, { summary: 'Offline' });
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

    it('reports a failure of the merge after a conflict', async () => {
      const api = fakeApi({
        get: jest.fn(() => of(makeEvent({ rev: 5 }))),
        draft: jest.fn(() =>
          of({ baseRev: 3, fields: { costText: '5 €' }, updatedAt: '2026-10-18T12:02:00Z' }),
        ),
        patch: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
      });
      const { toasts } = await setup(api);
      await userEvent.click(await screen.findByRole('button', { name: 'Übernehmen' }));
      expect(toasts().at(-1)).toContain('Das hat nicht geklappt');
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

    it('falls back to a reload when the refresh after a refused change fails', async () => {
      const stale = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'invalid_state' },
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

  it('still renders when the lookups and the revisions fail', async () => {
    const down = () => throwError(() => new HttpErrorResponse({ status: 500 }));
    const api = fakeApi({
      get: jest.fn(() => of(makeEvent({ state: 'published', editableFields: ['summary'] }))),
      categories: jest.fn(down),
      venues: jest.fn(down),
      revisions: jest.fn(down),
      hints: jest.fn(down),
    });
    await setup(api);
    await userEvent.click(screen.getByRole('button', { name: 'Eckdaten' }));
    expect(screen.getByLabelText('Kurztext')).toBeEnabled();
    expect(screen.queryByText(/Fehlt noch/)).not.toBeInTheDocument();
  });
});
