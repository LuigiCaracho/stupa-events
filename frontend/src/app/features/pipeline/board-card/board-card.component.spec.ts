import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeCard } from '../../../../testing/event-fixtures';
import { BoardCardComponent } from './board-card.component';

const blocker = (code: string, key: string) => ({
  code,
  field: null,
  severity: 'blocker' as const,
  messageKey: key,
  fixAction: null,
});

describe('BoardCardComponent', () => {
  it('shows title, day, organization, venue and the avatar of the creator', async () => {
    const { container } = await render(BoardCardComponent, { inputs: { card: makeCard() } });
    const button = screen.getByRole('button', { name: /Movienight/ });
    expect(button).toHaveTextContent('Do., 5. Nov.');
    expect(button).toHaveTextContent('FSI · Kinosaal 9-133');
    expect(screen.getByRole('img', { name: 'Mara Keller' })).toHaveTextContent('MK');
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('says "Ohne Organisation" and a question mark for an unknown creator', async () => {
    await render(BoardCardComponent, {
      inputs: {
        card: makeCard({
          organization: null,
          venueLabel: null,
          createdBy: { sub: 'x', displayName: null },
        }),
      },
    });
    expect(screen.getByRole('button')).toHaveTextContent('Ohne Organisation');
    expect(screen.getByRole('img', { name: '?' })).toBeInTheDocument();
  });

  it('lists the first three blockers and counts the rest', async () => {
    const blockers = [
      blocker('image_required', 'guards.image_required'),
      blocker('venue_missing', 'guards.venue_missing'),
      blocker('start_in_past', 'guards.start_in_past'),
    ];
    await render(BoardCardComponent, { inputs: { card: makeCard({ blockers, blockerCount: 5 }) } });
    expect(screen.getByText('Poster fehlt oder ist nicht freigegeben.')).toBeInTheDocument();
    expect(screen.getByText('Ort fehlt.')).toBeInTheDocument();
    expect(screen.getByText('+ 2 weitere')).toBeInTheDocument();
  });

  it.each([
    [{ state: 'approved' as const, publishAt: '2026-11-01T10:00:00Z' }, 'Geplant ab 01.11.'],
    [{ state: 'approved' as const }, 'Freigegeben'],
    [{ state: 'live' as const }, 'Veröffentlicht'],
    [{ state: 'live' as const, publicStatus: 'cancelled' as const }, 'Abgesagt'],
    [{ state: 'live' as const, publicStatus: 'postponed' as const }, 'Verschoben'],
  ])('reads %j as "%s"', async (overrides, text) => {
    await render(BoardCardComponent, { inputs: { card: makeCard(overrides) } });
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('shows no state line for a card in planning and the open questions when there are some', async () => {
    const { container } = await render(BoardCardComponent, {
      inputs: { card: makeCard({ openQuestions: 2 }) },
    });
    expect(container.querySelector('.bc__status')).toBeNull();
    expect(screen.getByText('2 Rückfragen')).toBeInTheDocument();
  });

  it('reports the lift and the click', async () => {
    const open = jest.fn();
    await render(BoardCardComponent, {
      inputs: { card: makeCard(), lifted: true, describedBy: 'bv-hint' },
      on: { open },
    });
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-pressed', 'true');
    expect(button).toHaveAttribute('aria-describedby', 'bv-hint');
    expect(button).toHaveAttribute('data-card-id', 'ev-1');
    await userEvent.click(button);
    expect(open).toHaveBeenCalledWith(expect.objectContaining({ id: 'ev-1' }));
  });

  it('warns in text when the howto of an archived dossier is unchecked', async () => {
    await render(BoardCardComponent, { inputs: { card: makeCard({ state: 'archived', howtoUnverified: true }) } });
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('shows no such warning for a normal card', async () => {
    await render(BoardCardComponent, { inputs: { card: makeCard() } });
    expect(screen.queryByText('Anleitung ungeprüft')).not.toBeInTheDocument();
  });
});
