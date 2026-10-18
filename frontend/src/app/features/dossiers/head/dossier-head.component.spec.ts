import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import type { EventDto } from '../api/event.models';
import { DossierHeadComponent, type HeadCommand } from './dossier-head.component';

async function setup(event: EventDto, actions: string[] = []) {
  const commands: HeadCommand[] = [];
  const view = await render(DossierHeadComponent, {
    inputs: { event, actions },
    on: { command: (c: HeadCommand) => commands.push(c) },
  });
  return { view, commands };
}

async function menuLabels(): Promise<string[]> {
  await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
  return screen.getAllByRole('menuitem').map((i) => i.textContent?.trim() ?? '');
}

describe('DossierHeadComponent', () => {
  it('shows title, state, time and organization', async () => {
    await setup(makeEvent());
    expect(screen.getByRole('heading', { level: 1, name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByText('Planung', { selector: 'app-status-text' })).toBeInTheDocument();
    expect(screen.getByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText(/19:00 – .*22:00/)).toBeInTheDocument();
  });

  it('marks the current state in the bar of the main path', async () => {
    await setup(makeEvent({ state: 'in_review' }));
    const steps = screen.getByRole('list', { name: 'Stand in der Pipeline' });
    const labels = within(steps)
      .getAllByRole('listitem')
      .map((li) => li.textContent?.trim());
    expect(labels).toEqual([
      'Idee',
      'Planung',
      'Freigabe angefragt',
      'Freigegeben',
      'Veröffentlicht',
      'Nachbereitung',
    ]);
    expect(within(steps).getByText('Freigabe angefragt')).toHaveAttribute('aria-current', 'step');
  });

  it('shows no bar for an archived or withdrawn dossier', async () => {
    await setup(makeEvent({ state: 'withdrawn', allowedTransitions: [] }));
    expect(screen.queryByRole('list', { name: 'Stand in der Pipeline' })).not.toBeInTheDocument();
  });

  it('says "Ohne Organisation" for a proposal', async () => {
    await setup(makeEvent({ organization: null }));
    expect(screen.getByText('Ohne Organisation')).toBeInTheDocument();
  });

  it.each([
    ['idea', 'T01', 'Planung starten'],
    ['planning', 'T02', 'Freigabe anfragen'],
    ['in_review', 'T04', 'Freigeben'],
    ['approved', 'T05', 'Veröffentlichen'],
    ['followup', 'T09', 'Nachbereitung abschließen'],
  ] as const)(
    'puts %s on the primary button %s when the server allows it',
    async (state, id, label) => {
      const { commands } = await setup(makeEvent({ state, allowedTransitions: [id] }));
      await userEvent.click(screen.getByRole('button', { name: label }));
      expect(commands).toEqual([{ kind: 'transition', id }]);
    },
  );

  it('shows no primary button when the server does not allow the transition', async () => {
    await setup(makeEvent({ state: 'in_review', allowedTransitions: ['T03'] }));
    expect(screen.queryByRole('button', { name: 'Freigeben' })).not.toBeInTheDocument();
  });

  it('lists the other transitions and the actions in the menu and runs them', async () => {
    const { commands } = await setup(
      makeEvent({ state: 'live', allowedTransitions: ['T07', 'T08'], publicStatus: 'cancelled' }),
      [
        'cancel',
        'postpone',
        'reinstate',
        'confirm-flyer',
        'image-exception',
        'assign-organization',
        'revert-revision',
      ],
    );
    expect(await menuLabels()).toEqual([
      'Absagen oder verschieben',
      'Absage zurücknehmen',
      'Flyer geprüft',
      'Ausnahme ohne Bild',
      'Organisation zuweisen',
      'Offline nehmen',
    ]);
    await userEvent.click(screen.getByRole('menuitem', { name: 'Offline nehmen' }));
    expect(commands).toEqual([{ kind: 'transition', id: 'T07' }]);
  });

  it('runs an action of the menu', async () => {
    const { commands } = await setup(makeEvent({ state: 'live', allowedTransitions: [] }), [
      'cancel',
    ]);
    await menuLabels();
    await userEvent.click(screen.getByRole('menuitem', { name: 'Absagen oder verschieben' }));
    expect(commands).toEqual([{ kind: 'action', name: 'cancel' }]);
  });

  it('offers the reinstatement only for a cancelled or postponed event', async () => {
    await setup(makeEvent({ state: 'live', allowedTransitions: [] }), ['reinstate']);
    expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument();
  });

  it('shows no menu when nothing is possible', async () => {
    await setup(makeEvent({ state: 'archived', allowedTransitions: [] }));
    expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument();
  });

  it.each([
    [
      'cancelled' as const,
      { code: 'illness' as const, text: 'Wir holen es nach' },
      'Abgesagt · Krankheit · Wir holen es nach',
    ],
    ['postponed' as const, { code: 'none' as const, text: null }, 'Verschoben'],
  ])(
    'writes the public status %s with its reason as text',
    async (publicStatus, publicReason, text) => {
      await setup(makeEvent({ state: 'live', publicStatus, publicReason, allowedTransitions: [] }));
      expect(screen.getByText(text)).toBeInTheDocument();
    },
  );

  it('has no axe violations with the menu open', async () => {
    const { view } = await setup(makeEvent({ allowedTransitions: ['T02', 'T11'] }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    expect(within(document.body).getByRole('menu')).toBeInTheDocument();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
