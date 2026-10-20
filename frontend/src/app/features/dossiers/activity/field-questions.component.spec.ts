import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { CommentsApi } from '../api/comments-api.service';
import type { CommentThread } from '../model/comment.models';
import { FieldQuestionsComponent } from './field-questions.component';

const open = (field: string): CommentThread =>
  ({ id: field, anchor: { field }, resolvedAt: null, replies: [] }) as unknown as CommentThread;

describe('FieldQuestionsComponent', () => {
  it('marks the fields with an open question and offers a button for every field', async () => {
    const show = jest.fn();
    await render(FieldQuestionsComponent, {
      inputs: {
        eventId: 'e1',
        canComment: true,
        threads: [
          open('hero'),
          { ...open('title'), resolvedAt: 'x' },
          { id: 'a', anchor: { attachmentId: 'a' }, resolvedAt: null } as unknown as CommentThread,
        ],
      },
      on: { show },
      providers: [{ provide: CommentsApi, useValue: { add: jest.fn() } }],
    });
    expect(screen.getAllByRole('button', { name: /^Rückfrage zu / })).toHaveLength(6);
    expect(screen.getAllByText('Rückfrage offen')).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage offen' }));
    expect(show).toHaveBeenCalled();
  });

  it('has no question buttons for a reader', async () => {
    await render(FieldQuestionsComponent, { inputs: { eventId: 'e1', canComment: false } });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
