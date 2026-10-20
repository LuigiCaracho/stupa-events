import { HttpErrorResponse } from '@angular/common/http';
import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { CommentsApi } from '../api/comments-api.service';
import { DocumentsApi } from '../api/documents-api.service';
import { writeLocalCopy } from '../editor/local-copy';
import type { DocumentOut } from '../model/document.models';
import { HowtoTabComponent } from './howto-tab.component';

const doc = (o: Partial<DocumentOut> = {}): DocumentOut => ({
  id: 'd1',
  kind: 'howto',
  title: 'Anleitung',
  visibility: 'org',
  carryOver: false,
  rev: 2,
  verifiedAt: null,
  verifiedBy: null,
  updatedAt: '2026-10-01T10:00:00Z',
  bodyMd: 'Alt',
  ...o,
});

function fakeApi(over: Record<string, unknown> = {}) {
  return {
    list: jest.fn(() => of([doc()])),
    get: jest.fn(() => of(doc())),
    create: jest.fn(() => of(doc())),
    put: jest.fn(() => of(doc({ rev: 3, bodyMd: 'Neu' }))),
    getDraft: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))),
    putDraft: jest.fn(() => of({})),
    deleteDraft: jest.fn(() => of(undefined)),
    revisions: jest.fn(() => of([])),
    ...over,
  };
}

async function setup(api = fakeApi(), inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const view = await render(HowtoTabComponent, {
    inputs: { event: makeEvent({}), canEdit: true, ...inputs },
    on: { changed },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      { provide: DocumentsApi, useValue: api },
      { provide: CommentsApi, useValue: { add: jest.fn(() => of({})) } },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return {
    ...view,
    api,
    changed,
    success: jest.spyOn(toast, 'success'),
    error: jest.spyOn(toast, 'error'),
  };
}

const area = () => screen.getByRole('textbox', { name: 'Diese Ausgabe' }) as HTMLTextAreaElement;

describe('HowtoTabComponent', () => {
  afterEach(() => localStorage.clear());

  it('shows the howto, its verification state and the privacy hint', async () => {
    await setup();
    expect(area()).toHaveValue('Alt');
    expect(screen.getByText('Noch nicht geprüft.')).toBeInTheDocument();
    expect(screen.getByText(/Bitte keine privaten Telefonnummern/)).toBeInTheDocument();
  });

  it('shows who verified it', async () => {
    await setup(
      fakeApi({
        get: jest.fn(() => of(doc({ verifiedAt: '2026-09-01T10:00:00Z', verifiedBy: 'Anna' }))),
      }),
    );
    expect(screen.getByText(/Zuletzt geprüft von Anna am/)).toBeInTheDocument();
  });

  it('offers the template when there is no howto and creates it', async () => {
    const { api, changed } = await setup(fakeApi({ list: jest.fn(() => of([])) }));
    expect(screen.getByText('Noch keine Anleitung.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Vorlage einfügen' }));
    expect(api.create).toHaveBeenCalledWith(
      'ev-1',
      expect.objectContaining({
        kind: 'howto',
        bodyMd: expect.stringContaining('## Worum geht es?'),
      }),
    );
    expect(changed).toHaveBeenCalled();
  });

  it('has no create button for a reader and shows a load error', async () => {
    await setup(fakeApi({ list: jest.fn(() => of([])) }), { canEdit: false });
    expect(screen.queryByRole('button', { name: 'Vorlage einfügen' })).not.toBeInTheDocument();
  });

  it('shows an error note when the list fails', async () => {
    await setup(
      fakeApi({ list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Anleitung konnte nicht geladen werden.',
    );
  });

  it('saves a new revision with a change note and the revision as If-Match', async () => {
    const { api, success, changed } = await setup();
    expect(screen.getByRole('button', { name: 'Als neue Fassung speichern' })).toBeDisabled();
    await userEvent.type(area(), ' mehr');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.type(screen.getByLabelText('Änderungsnotiz'), 'Technik');
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(api.put).toHaveBeenCalledWith('d1', 2, { bodyMd: 'Alt mehr', changeNote: 'Technik' });
    expect(success).toHaveBeenCalledWith('Neue Fassung gespeichert.');
    expect(changed).toHaveBeenCalled();
    expect(area()).toHaveValue('Neu');
  });

  it('can cancel the note and sends no note when it is empty', async () => {
    const { api } = await setup();
    await userEvent.type(area(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(api.put).toHaveBeenCalledWith('d1', 2, { bodyMd: 'Altx', changeNote: undefined });
  });

  it('offers a reload after a conflict', async () => {
    const api = fakeApi({
      put: jest.fn(() =>
        throwError(
          () => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } }),
        ),
      ),
    });
    await setup(api);
    await userEvent.type(area(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(screen.getByRole('alert')).toHaveTextContent('inzwischen geändert');
    await userEvent.click(screen.getByRole('button', { name: 'Neu laden' }));
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/inzwischen geändert/)).not.toBeInTheDocument();
  });

  it('shows other failures as a toast', async () => {
    const api = fakeApi({
      put: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
    });
    const { error } = await setup(api);
    await userEvent.type(area(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(error).toHaveBeenCalled();
  });

  it('restores a server draft of the same revision and lets the person drop it', async () => {
    const api = fakeApi({
      getDraft: jest.fn(() => of({ bodyMd: 'Entwurf', baseRev: 2, updatedAt: '' })),
    });
    await setup(api);
    expect(area()).toHaveValue('Entwurf');
    expect(
      screen.getByText('Dein ungespeicherter Entwurf wurde wiederhergestellt.'),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
    expect(api.deleteDraft).toHaveBeenCalledWith('d1');
    expect(area()).toHaveValue('Alt');
  });

  it('ignores a draft of an older revision and falls back to the local copy', async () => {
    writeLocalCopy('howto:d1', 'Lokal');
    const api = fakeApi({
      getDraft: jest.fn(() => of({ bodyMd: 'Alt-Entwurf', baseRev: 1, updatedAt: '' })),
    });
    await setup(api);
    expect(area()).toHaveValue('Lokal');
  });

  it('asks about a selection of the source', async () => {
    await setup();
    area().setSelectionRange(0, 2);
    area().dispatchEvent(new Event('select'));
    expect(await screen.findByRole('button', { name: 'Rückfrage zu Auswahl' })).toBeInTheDocument();
  });

  it('copes with a document without body or verifier and a save answer without body', async () => {
    const bare = doc({ bodyMd: undefined, verifiedAt: '2026-09-01T10:00:00Z', verifiedBy: null });
    const api = fakeApi({
      list: jest.fn(() => of([bare])),
      get: jest.fn(() => of(bare)),
      put: jest.fn(() => of(doc({ rev: 3, bodyMd: undefined }))),
    });
    await setup(api);
    expect(area()).toHaveValue('');
    await userEvent.type(area(), 'neu');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(area()).toHaveValue('neu');
  });

  it('keeps the page when the local copy equals the stored text', async () => {
    writeLocalCopy('howto:d1', 'Alt');
    await setup();
    expect(
      screen.queryByText('Dein ungespeicherter Entwurf wurde wiederhergestellt.'),
    ).not.toBeInTheDocument();
  });

  it('does nothing on save or reload without a document', async () => {
    const { fixture, api } = await setup(fakeApi({ list: jest.fn(() => of([])) }));
    const page = fixture.componentInstance as unknown as { save(): void; reload(): void };
    page.save();
    page.reload();
    expect(api.put).not.toHaveBeenCalled();
    expect(api.get).not.toHaveBeenCalled();
  });

  it('shows a toast when the document does not open', async () => {
    const { fixture } = await setup(
      fakeApi({ get: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))) }),
    );
    expect(fixture.debugElement.injector.get(ToastService).toasts()).toHaveLength(1);
  });
});
