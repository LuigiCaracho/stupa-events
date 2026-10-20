import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { AuthService } from '@core/auth/auth.service';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { AttachmentsApi } from '../api/attachments-api.service';
import { CommentsApi } from '../api/comments-api.service';
import { DocumentsApi } from '../api/documents-api.service';
import { EventsApi } from '../api/events-api.service';
import type { CommentThread } from '../model/comment.models';
import { ActivityTabComponent } from './activity-tab.component';

const thread = (o: Partial<CommentThread>): CommentThread => ({
  id: 't1',
  authorSub: 'me',
  authorName: 'Anna',
  actorType: 'human',
  bodyMd: 'Frage',
  anchor: { field: 'hero' },
  parentId: null,
  resolvedAt: null,
  resolvedBy: null,
  createdAt: '2026-10-01T10:00:00Z',
  replies: [],
  ...o,
});

const anchors: Record<string, CommentThread['anchor']> = {
  field: { field: 'title' },
  file: { attachmentId: 'a1' },
  item: { checklistItemId: 'c1' },
  doc: { documentId: 'd1', rev: 1, from: 0, to: 3 },
  none: null,
};

async function setup(
  threads: CommentThread[],
  inputs: Record<string, unknown> = {},
  comments: Record<string, unknown> = {},
) {
  const commentsApi = {
    add: jest.fn(() => of({})),
    resolve: jest.fn(() => of({})),
    reopen: jest.fn(() => of({})),
    ...comments,
  };
  const changed = jest.fn();
  const revert = jest.fn();
  const view = await render(ActivityTabComponent, {
    inputs: { event: makeEvent({ rev: 3 }), threads, canComment: true, canRevert: true, ...inputs },
    on: { changed, revert },
    providers: [
      { provide: CommentsApi, useValue: commentsApi },
      {
        provide: EventsApi,
        useValue: {
          revisions: jest.fn(() =>
            of({
              items: [
                {
                  rev: 3,
                  at: '2026-10-02T10:00:00Z',
                  actor: { sub: 'u', displayName: 'Ben' },
                  actorType: 'human',
                  fieldClass: 'text',
                  changeNote: null,
                  changedFields: ['title'],
                },
                {
                  rev: 2,
                  at: '2026-10-01T10:00:00Z',
                  actor: { sub: 'u', displayName: 'Ben' },
                  actorType: 'human',
                  fieldClass: 'state',
                  changeNote: 'n',
                  changedFields: [],
                },
              ],
              total: 2,
              limit: 100,
              offset: 0,
            }),
          ),
        },
      },
      {
        provide: DocumentsApi,
        useValue: {
          list: jest.fn(() => of([{ id: 'd1' }])),
          revisions: jest.fn(() =>
            of([
              {
                rev: 1,
                actorId: 'u',
                actorType: 'human',
                changeNote: null,
                at: '2026-10-01T12:00:00Z',
                titleChanged: false,
                charsDelta: 5,
              },
            ]),
          ),
        },
      },
      {
        provide: AttachmentsApi,
        useValue: { list: jest.fn(() => of([{ id: 'a1', displayName: 'plan.pdf' }])) },
      },
      { provide: AuthService, useValue: { userId: () => 'me', can: () => false, roles: () => [] } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, commentsApi, changed, revert, error: jest.spyOn(toast, 'error') };
}

describe('ActivityTabComponent', () => {
  it('shows the guard sentence while a question on the poster is open', async () => {
    const { container } = await setup([thread({})]);
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent(
      'Eine offene Rückfrage am Poster blockiert die Freigabe.',
    );
    expect(screen.getByRole('button', { name: 'Poster' })).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('merges revisions, transitions, howto revisions and comments into one timeline', async () => {
    await setup([thread({ resolvedAt: '2026-10-03T10:00:00Z' })]);
    expect(screen.getByText('Fassung 3 gespeichert')).toBeInTheDocument();
    expect(screen.getByText('Statuswechsel (Fassung 2)')).toBeInTheDocument();
    expect(screen.getByText('Anleitung, Fassung 1')).toBeInTheDocument();
    expect(screen.getAllByText('Rückfrage erledigt').length).toBeGreaterThan(0);
  });

  it('labels every kind of anchor', async () => {
    await setup(Object.values(anchors).map((anchor, i) => thread({ id: `t${i}`, anchor })));
    for (const label of [
      'am Feld Titel',
      'an Anhang plan.pdf',
      'an einem Checklistenpunkt',
      'in der Anleitung',
      'Allgemein',
    ]) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
    }
  });

  it('says so without questions and without a timeline', async () => {
    await setup([], { canComment: false, canRevert: false });
    expect(screen.getByText('Noch keine Rückfragen.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Allgemeine Rückfrage' })).not.toBeInTheDocument();
    expect(screen.queryByText('Fassungen und Zurücksetzen')).not.toBeInTheDocument();
  });

  it('replies, resolves and reopens', async () => {
    const { commentsApi, changed } = await setup([
      thread({ anchor: null }),
      thread({ id: 't2', resolvedAt: '2026-10-02T10:00:00Z', anchor: null }),
    ]);
    await userEvent.click(screen.getByRole('button', { name: 'Antworten' }));
    await userEvent.type(screen.getByLabelText('Deine Antwort'), 'Ja');
    await userEvent.click(screen.getByRole('button', { name: 'Senden' }));
    expect(commentsApi.add).toHaveBeenCalledWith('ev-1', { bodyMd: 'Ja', parentId: 't1' });
    await userEvent.click(screen.getByRole('button', { name: 'Erledigt' }));
    expect(commentsApi.resolve).toHaveBeenCalledWith('t1');
    await userEvent.click(screen.getByText('1 erledigte Rückfragen'));
    await userEvent.click(screen.getByRole('button', { name: 'Wieder öffnen' }));
    expect(commentsApi.reopen).toHaveBeenCalledWith('t2');
    expect(changed).toHaveBeenCalledTimes(3);
  });

  it('lets only the author, reviewers and editors resolve', async () => {
    await setup([thread({ authorSub: 'other', anchor: null })]);
    expect(screen.queryByRole('button', { name: 'Erledigt' })).not.toBeInTheDocument();
  });

  it('shows a refusal as a toast', async () => {
    const { error } = await setup(
      [thread({ anchor: null })],
      {},
      { resolve: jest.fn(() => throwError(() => new Error('x'))) },
    );
    await userEvent.click(screen.getByRole('button', { name: 'Erledigt' }));
    expect(error).toHaveBeenCalled();
  });

  it('offers the revert list to reviewers', async () => {
    await setup([]);
    expect(screen.getByRole('heading', { name: 'Fassungen und Zurücksetzen' })).toBeInTheDocument();
  });
});
