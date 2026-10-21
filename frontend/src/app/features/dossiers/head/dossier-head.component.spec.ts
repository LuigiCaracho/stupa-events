import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import type { EventAction, EventDto } from '../api/event.models';
import { DossierHeadComponent, type HeadCommand } from './dossier-head.component';

async function setup(event: EventDto, inputs: { howtoUnverified?: boolean; busy?: boolean } = {}) {
  const commands: HeadCommand[] = [];
  const view = await render(DossierHeadComponent, {
    inputs: { event, ...inputs },
    on: { command: (c: HeadCommand) => commands.push(c) },
    providers: [provideRouter([])],
  });
  return { view, commands };
}

const withActions = (allowedActions: EventAction[], over: Partial<EventDto> = {}) =>
  makeEvent({ allowedActions, ...over });

async function menuLabels(): Promise<string[]> {
  await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
  return screen.getAllByRole('menuitem').map((i) => i.textContent?.trim() ?? '');
}

describe('DossierHeadComponent', () => {
  it('shows title, state, time, organization, venue and category', async () => {
    await setup(makeEvent());
    expect(screen.getByRole('heading', { level: 1, name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByText('Entwurf', { selector: 'app-status-text' })).toBeInTheDocument();
    expect(screen.getByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText(/19:00 – .*22:00/)).toBeInTheDocument();
    expect(screen.getByText('Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('Kino')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Alle Events' })).toHaveAttribute('href', '/dossiers');
  });

  it('says "Ohne Organisation" for an old draft without one', async () => {
    await setup(makeEvent({ organization: null }));
    expect(screen.getByText('Ohne Organisation')).toBeInTheDocument();
  });

  it.each([
    ['publish', 'Veröffentlichen'],
    ['unpublish', 'Zurückziehen'],
    ['cancel', 'Absagen'],
    ['postpone', 'Verschieben'],
    ['reinstate', 'Wieder ansetzen'],
    ['archive', 'Archivieren'],
    ['restore', 'Wiederherstellen'],
    ['clone', 'Neu aus diesem Event'],
  ] as const)('puts the action %s on the button "%s" and sends it', async (action, label) => {
    const { commands } = await setup(withActions([action]));
    await userEvent.click(screen.getByRole('button', { name: label }));
    expect(commands).toEqual([action]);
  });

  it('shows exactly the actions the server lists, in the order of the bar', async () => {
    await setup(withActions(['archive', 'cancel', 'unpublish', 'revert-revision', 'verify-howto']));
    const names = screen
      .getAllByRole('button')
      .map((b) => b.textContent?.trim())
      .filter(Boolean);
    expect(names).toEqual(['Zurückziehen', 'Absagen', 'Archivieren']);
    expect(screen.getByRole('group', { name: 'Aktionen' })).toBeInTheDocument();
  });

  it('shows no bar and no menu when nothing is allowed', async () => {
    await setup(withActions([], { state: 'archived' }));
    expect(screen.queryByRole('group', { name: 'Aktionen' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument();
  });

  it('waits while a call runs', async () => {
    await setup(withActions(['publish']), { busy: true });
    expect(screen.getByRole('button', { name: 'Veröffentlichen' })).toBeDisabled();
  });

  it('keeps "Als Format speichern" and "Ort bestätigen" in the menu', async () => {
    const { commands } = await setup(withActions(['save-as-format', 'confirm-location']));
    expect(await menuLabels()).toEqual(['Ort bestätigen', 'Als Format speichern']);
    await userEvent.click(screen.getByRole('menuitem', { name: 'Als Format speichern' }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Ort bestätigen' }));
    expect(commands).toEqual(['save-as-format', 'confirm-location']);
  });

  it.each([
    [
      'cancelled' as const,
      { code: 'illness' as const, text: 'Wir holen es nach' },
      'Abgesagt · Krankheit · Wir holen es nach',
    ],
    ['postponed' as const, { code: 'none' as const, text: null }, 'Verschoben'],
  ])('writes the public status %s with its reason as text', async (publicStatus, publicReason, text) => {
    await setup(makeEvent({ state: 'published', publicStatus, publicReason }));
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('links the format and warns in text when the archived howto is unverified', async () => {
    const { view } = await setup(
      makeEvent({ state: 'archived', format: { slug: 'movienight', title: 'Movienight' } }),
      { howtoUnverified: true },
    );
    expect(screen.getByRole('link', { name: 'Movienight' })).toHaveAttribute(
      'href',
      '/formate/movienight',
    );
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('shows no warning when the howto is checked', async () => {
    await setup(makeEvent({ state: 'archived' }));
    expect(screen.queryByText('Anleitung ungeprüft')).not.toBeInTheDocument();
  });

  it('has no axe violations with the menu open', async () => {
    const { view } = await setup(withActions(['publish', 'save-as-format']));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
