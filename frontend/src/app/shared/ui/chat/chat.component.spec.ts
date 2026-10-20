import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import type { CommentThread } from '../../../features/dossiers/model/comment.models';
import { ChatComponent } from './chat.component';

const thread = (o: Partial<CommentThread> = {}): CommentThread => ({
  id: 't1',
  authorSub: 'u1',
  authorName: 'Anna',
  actorType: 'human',
  bodyMd: 'Passt das Bild?',
  anchor: { field: 'hero' },
  parentId: null,
  resolvedAt: null,
  resolvedBy: null,
  createdAt: '2026-10-01T10:00:00Z',
  replies: [
    {
      id: 'r1',
      authorSub: 'u2',
      authorName: 'Ben',
      actorType: 'human',
      bodyMd: 'Ja',
      anchor: null,
      parentId: 't1',
      resolvedAt: null,
      resolvedBy: null,
      createdAt: '2026-10-01T11:00:00Z',
    },
  ],
  ...o,
});

async function setup(threads: CommentThread[], extra: Record<string, unknown> = {}) {
  const on = { reply: jest.fn(), resolve: jest.fn(), reopen: jest.fn(), jump: jest.fn() };
  const view = await render(ChatComponent, {
    inputs: {
      threads,
      anchorLabel: () => 'Poster',
      canWrite: true,
      canResolve: () => true,
      ...extra,
    },
    on,
  });
  return { ...view, on };
}

describe('ChatComponent', () => {
  it('shows the anchor chip, the state as text and the replies', async () => {
    const { container } = await setup([thread()]);
    expect(screen.getByRole('button', { name: 'Poster' })).toBeInTheDocument();
    expect(screen.getByText('Offen')).toBeInTheDocument();
    expect(screen.getByText('Passt das Bild?')).toBeInTheDocument();
    expect(screen.getByText('Ja')).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('jumps, resolves and reopens', async () => {
    const { on } = await setup([
      thread(),
      thread({ id: 't2', resolvedAt: '2026-10-02T10:00:00Z', replies: [] }),
    ]);
    await userEvent.click(screen.getAllByRole('button', { name: 'Poster' })[0]);
    expect(on.jump).toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Erledigt' }));
    expect(on.resolve).toHaveBeenCalledWith('t1');
    expect(screen.getByText('Erledigt', { selector: 'app-status-text' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Wieder öffnen' }));
    expect(on.reopen).toHaveBeenCalledWith('t2');
  });

  it('sends a reply and ignores an empty one', async () => {
    const { on } = await setup([thread()]);
    await userEvent.click(screen.getByRole('button', { name: 'Antworten' }));
    await userEvent.click(screen.getByRole('button', { name: 'Senden' }));
    expect(on.reply).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText('Deine Antwort'), 'Danke');
    await userEvent.click(screen.getByRole('button', { name: 'Senden' }));
    expect(on.reply).toHaveBeenCalledWith({ parentId: 't1', bodyMd: 'Danke' });
    expect(screen.queryByLabelText('Deine Antwort')).not.toBeInTheDocument();
  });

  it('can cancel a reply and hides write controls for readers', async () => {
    await setup([thread()]);
    await userEvent.click(screen.getByRole('button', { name: 'Antworten' }));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(screen.queryByLabelText('Deine Antwort')).not.toBeInTheDocument();
  });

  it('shows no actions to a reader', async () => {
    await setup([thread()], { canWrite: false, canResolve: () => false });
    expect(screen.queryByRole('button', { name: 'Antworten' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Erledigt' })).not.toBeInTheDocument();
  });
});
