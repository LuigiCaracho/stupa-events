import { HttpErrorResponse } from '@angular/common/http';
import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { DocumentsApi } from '../api/documents-api.service';
import { RETROSPECTIVE_SCAFFOLD, RetrospectiveComponent } from './retrospective.component';

const doc = {
  id: 'r1', kind: 'retrospective', title: 'Rückblick', visibility: 'org', carryOver: false, rev: 1,
  verifiedAt: null, verifiedBy: null, updatedAt: '2026-10-01T10:00:00Z', bodyMd: 'Gut gelaufen',
};

async function setup(api: Record<string, unknown> = {}, inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const fake = {
    list: jest.fn(() => of([])),
    create: jest.fn(() => of(doc)),
    get: jest.fn(() => of(doc)),
    getDraft: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))),
    putDraft: jest.fn(() => of({})),
    put: jest.fn(() => of(doc)),
    deleteDraft: jest.fn(() => of(undefined)),
    ...api,
  };
  const view = await render(RetrospectiveComponent, {
    inputs: { event: makeEvent({ state: 'archived' }), canEdit: true, ...inputs },
    on: { changed },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      { provide: DocumentsApi, useValue: fake },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, fake, changed };
}

describe('RetrospectiveComponent', () => {
  afterEach(() => localStorage.clear());

  it('starts an empty retrospective with the scaffold and creates the document on the first save', async () => {
    const { fake, changed } = await setup();
    const area = screen.getByRole('textbox', { name: 'Rückblick' });
    expect(area).toHaveValue(RETROSPECTIVE_SCAFFOLD);
    await userEvent.click(screen.getByRole('button', { name: 'Rückblick speichern' }));
    expect(fake.list).toHaveBeenCalledWith('ev-1', 'retrospective');
    expect(fake.create).toHaveBeenCalledWith('ev-1', {
      kind: 'retrospective',
      title: 'Rückblick',
      bodyMd: RETROSPECTIVE_SCAFFOLD,
      visibility: 'org',
      carryOver: false,
    });
    expect(changed).toHaveBeenCalled();
  });

  it('opens the existing retrospective in the document editor', async () => {
    await setup({ list: jest.fn(() => of([doc])) });
    expect(await screen.findByRole('textbox', { name: 'Rückblick' })).toHaveValue('Gut gelaufen');
    expect(screen.queryByRole('button', { name: 'Rückblick speichern' })).not.toBeInTheDocument();
  });

  it('reloads when somebody created it in the meantime', async () => {
    const list = jest.fn().mockReturnValueOnce(of([])).mockReturnValue(of([doc]));
    await setup({
      list,
      create: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'already_exists' } }))),
    });
    await userEvent.click(screen.getByRole('button', { name: 'Rückblick speichern' }));
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: 'Rückblick' })).toHaveValue('Gut gelaufen'),
    );
  });

  it('says so when there is none and the person cannot write', async () => {
    await setup(undefined, { canEdit: false });
    expect(screen.getByText('Noch kein Rückblick.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rückblick speichern' })).not.toBeInTheDocument();
  });

  it('shows an error note when the list does not load', async () => {
    await setup({ list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) });
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Rückblick konnte nicht geladen werden.');
  });

  it('shows the message of any other refusal when creating', async () => {
    const { fake } = await setup({
      create: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    });
    await userEvent.click(screen.getByRole('button', { name: 'Rückblick speichern' }));
    expect(fake.create).toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Rückblick speichern' })).toBeEnabled();
  });
});
