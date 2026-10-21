import { HttpErrorResponse } from '@angular/common/http';
import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { DocumentsApi } from '../api/documents-api.service';
import type { DocumentOut } from '../model/document.models';
import { DocumentEditorComponent } from './document-editor.component';
import { writeLocalCopy } from './local-copy';

const doc = (o: Partial<DocumentOut> = {}): DocumentOut => ({
  id: 'd1',
  kind: 'retrospective',
  title: 'Rückblick',
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
    get: jest.fn(() => of(doc())),
    put: jest.fn(() => of(doc({ rev: 3, bodyMd: 'Neu' }))),
    getDraft: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))),
    putDraft: jest.fn(() => of({})),
    deleteDraft: jest.fn(() => of(undefined)),
    ...over,
  };
}

async function setup(api = fakeApi(), inputs: Record<string, unknown> = {}) {
  const saved = jest.fn();
  const view = await render(DocumentEditorComponent, {
    inputs: { documentId: 'd1', canEdit: true, label: 'Rückblick', keyPrefix: 'retro', ...inputs },
    on: { saved },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      { provide: DocumentsApi, useValue: api },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api, saved, success: jest.spyOn(toast, 'success'), error: jest.spyOn(toast, 'error') };
}

const area = () => screen.getByRole('textbox', { name: 'Rückblick' }) as HTMLTextAreaElement;

describe('DocumentEditorComponent', () => {
  afterEach(() => localStorage.clear());

  it('loads the document by id into the editor', async () => {
    const { api } = await setup();
    expect(api.get).toHaveBeenCalledWith('d1');
    expect(area()).toHaveValue('Alt');
  });

  it('saves a new revision with the revision as If-Match source and an optional note', async () => {
    const { api, saved, success } = await setup();
    await userEvent.type(area(), ' mehr');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.type(screen.getByLabelText(/Änderungsnotiz/), 'Kosten ergänzt');
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(api.put).toHaveBeenCalledWith('d1', 2, { bodyMd: 'Alt mehr', changeNote: 'Kosten ergänzt' });
    expect(saved).toHaveBeenCalledWith(expect.objectContaining({ rev: 3 }));
    expect(success).toHaveBeenCalledWith('Gespeichert.');
  });

  it('keeps the save button off until the text changed', async () => {
    await setup();
    expect(screen.getByRole('button', { name: 'Als neue Fassung speichern' })).toBeDisabled();
  });

  it('asks to reload on an edit conflict', async () => {
    const api = fakeApi({
      put: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'conflict' } }))),
    });
    await setup(api);
    await userEvent.type(area(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/geändert/);
    await userEvent.click(screen.getByRole('button', { name: 'Neu laden' }));
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('restores a draft of the same revision and lets the person drop it', async () => {
    const api = fakeApi({
      getDraft: jest.fn(() => of({ bodyMd: 'Entwurf', baseRev: 2, updatedAt: '2026-10-02T10:00:00Z' })),
    });
    await setup(api);
    expect(area()).toHaveValue('Entwurf');
    await userEvent.click(screen.getByRole('button', { name: 'Verwerfen' }));
    expect(area()).toHaveValue('Alt');
    expect(api.deleteDraft).toHaveBeenCalledWith('d1');
  });

  it('restores the local copy when the server has no draft', async () => {
    writeLocalCopy('retro:d1', 'Lokal');
    await setup();
    expect(area()).toHaveValue('Lokal');
  });

  it('shows a read-only editor and no save button without the right to edit', async () => {
    const { api } = await setup(fakeApi(), { canEdit: false });
    expect(screen.queryByRole('button', { name: 'Als neue Fassung speichern' })).not.toBeInTheDocument();
    expect(api.getDraft).not.toHaveBeenCalled();
  });

  it('says so when the document does not load and tries again', async () => {
    const get = jest.fn().mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 500 }))).mockReturnValue(of(doc()));
    await setup(fakeApi({ get }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Das Dokument konnte nicht geladen werden.');
    await userEvent.click(screen.getByRole('button', { name: 'Neu laden' }));
    expect(area()).toHaveValue('Alt');
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('shows the message of any other failure and keeps the text', async () => {
    const api = fakeApi({
      put: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    });
    const { error } = await setup(api);
    await userEvent.type(area(), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Als neue Fassung speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Fassung speichern' }));
    expect(error).toHaveBeenCalled();
    expect(area()).toHaveValue('Altx');
  });

  it('treats a document without text as empty', async () => {
    await setup(fakeApi({ get: jest.fn(() => of(doc({ bodyMd: undefined }))) }));
    expect(area()).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Als neue Fassung speichern' })).toBeDisabled();
  });
});
