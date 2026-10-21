import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { AttachmentsApi } from '../api/attachments-api.service';
import { CommentsApi } from '../api/comments-api.service';
import type { AttachmentOut } from '../model/attachment.models';
import type { CommentThread } from '../model/comment.models';
import { AttachmentsTabComponent } from './attachments-tab.component';

const file = (o: Partial<AttachmentOut>): AttachmentOut => ({
  id: 'a1',
  kind: 'social_post',
  displayName: 'post.png',
  mime: 'image/png',
  sizeBytes: 1000,
  visibility: 'org',
  scanStatus: 'clean',
  altText: 'Bild',
  credit: 'A',
  rightsBasis: 'own_work',
  licenseRef: null,
  sourceUrl: null,
  personsDepicted: false,
  consentNote: null,
  containsDate: null,
  datedFor: null,
  meta: {},
  supersedesId: null,
  retiredAt: null,
  createdAt: '2026-10-01T10:00:00Z',
  hasPreview: false,
  replacedBy: null,
  ...o,
});

function fakeApi(over: Partial<Record<keyof AttachmentsApi, unknown>> = {}) {
  return {
    list: jest.fn(() =>
      of([
        file({}),
        file({ id: 'a0', displayName: 'alt.png', retiredAt: '2026-09-01T10:00:00Z' }),
        file({ id: 'a2', kind: 'quote', displayName: 'angebot.pdf' }),
      ]),
    ),
    upload: jest.fn(() => of(file({}))),
    replace: jest.fn(() => of(file({}))),
    patch: jest.fn(() => of(file({}))),
    retire: jest.fn(() => of(undefined)),
    downloadUrl: (id: string) => `/dl/${id}`,
    previewUrl: (id: string) => `/pv/${id}`,
    ...over,
  };
}

async function setup(api = fakeApi(), inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const view = await render(AttachmentsTabComponent, {
    inputs: { event: makeEvent({}), canEdit: true, ...inputs },
    on: { changed },
    providers: [
      { provide: AttachmentsApi, useValue: api },
      { provide: CommentsApi, useValue: { add: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api, changed, error: jest.spyOn(toast, 'error') };
}

describe('AttachmentsTabComponent', () => {
  it('groups the files, folds older versions and never shows an empty group', async () => {
    const { container } = await setup();
    expect(screen.getByRole('heading', { name: 'Social-Posts' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Angebotsdateien' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Unterlagen' })).not.toBeInTheDocument();
    expect(screen.getByText('1 ältere Fassungen')).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('says so when there are no files and when loading fails', async () => {
    await setup(fakeApi({ list: jest.fn(() => of([])) }));
    expect(screen.getByText('Noch keine Anhänge.')).toBeInTheDocument();
  });

  it('shows an error note when the list fails', async () => {
    await setup(
      fakeApi({ list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Anhänge konnten nicht geladen werden.',
    );
  });

  it('marks a file with an open question', async () => {
    const thread = {
      id: 't',
      resolvedAt: null,
      anchor: { attachmentId: 'a1' },
    } as unknown as CommentThread;
    await setup(fakeApi(), { threads: [thread] });
    expect(screen.getByRole('button', { name: 'Rückfrage offen' })).toBeInTheDocument();
  });

  it('uploads and tells the page', async () => {
    const { api, changed, container } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Anhang hinzufügen' }));
    await userEvent.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['x'], 'plan.pdf', { type: 'application/pdf' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(api.upload).toHaveBeenCalledWith('ev-1', expect.objectContaining({ kind: 'other' }));
    expect(changed).toHaveBeenCalled();
    expect(api.list).toHaveBeenCalledTimes(2);
  });

  it('names size and limit when the file is too large', async () => {
    const big = new File([new ArrayBuffer(3 * 1_048_576)], 'gross.pdf', {
      type: 'application/pdf',
    });
    const api = fakeApi({
      upload: jest.fn(() =>
        throwError(
          () =>
            new HttpErrorResponse({
              status: 413,
              error: { status: 413, code: 'file_too_large', limitBytes: 1_048_576 },
            }),
        ),
      ),
    });
    const { error, container } = await setup(api);
    await userEvent.click(screen.getByRole('button', { name: 'Anhang hinzufügen' }));
    await userEvent.upload(container.querySelector('input[type="file"]') as HTMLInputElement, big);
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(error).toHaveBeenCalledWith('Die Datei ist 3,0 MB groß, erlaubt sind 1 MB.');
  });

  it('falls back to the generic text for any other failure', async () => {
    const api = fakeApi({
      retire: jest.fn(() =>
        throwError(
          () =>
            new HttpErrorResponse({ status: 409, error: { status: 409, code: 'poster_in_use' } }),
        ),
      ),
    });
    const { error } = await setup(api);
    await userEvent.click(screen.getAllByRole('button', { name: 'Aktionen für den Anhang' })[0]);
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Ausblenden' }));
    expect(error).toHaveBeenCalledWith(
      'Das Poster ist in Gebrauch und kann nicht ausgeblendet werden.',
    );
  });

  it('replaces, retires and changes the visibility', async () => {
    const doc = file({ kind: 'other', displayName: 'x.pdf', mime: 'application/pdf' });
    const { api, container } = await setup(fakeApi({ list: jest.fn(() => of([doc])) }));
    const menu = () => screen.getByRole('button', { name: 'Aktionen für den Anhang' });
    await userEvent.click(menu());
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Ausblenden' }));
    expect(api.retire).toHaveBeenCalledWith('a1');
    await userEvent.click(menu());
    await userEvent.click(await screen.findByText('Team'));
    expect(api.patch).toHaveBeenCalledWith('a1', { visibility: 'team' });
    await userEvent.click(menu());
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Ersetzen' }));
    expect(screen.getByText(/wird ersetzt/)).toBeInTheDocument();
    await userEvent.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['x'], 'neu.pdf', { type: 'application/pdf' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Hochladen' }));
    expect(api.replace).toHaveBeenCalledWith('a1', expect.objectContaining({ kind: 'other' }));
    expect(screen.queryByText(/wird ersetzt/)).not.toBeInTheDocument();
  });
});
