import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { render, screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { Subject, of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../testing/a11y';
import { fakeAuth } from '../../../testing/event-fixtures';
import { makeHit, makeSearch } from '../../../testing/m5-fixtures';
import { ArchiveApi } from '../../features/archive/api/archive-api.service';
import type { SearchOut } from '../../features/archive/model/archive.models';
import { DossierCommands } from '../../features/dossiers/api/dossier-commands';
import { NAV_ITEMS, NavService } from '../nav.service';
import { CommandPaletteComponent } from './command-palette.component';
import { PaletteService } from './palette.service';

const formatHit = makeHit({
  kind: 'format',
  id: 'movienight',
  title: 'Movienight',
  link: '/formate/movienight',
  subtitle: 'FSI',
});

function fakeArchive(over: Record<string, unknown> = {}) {
  return {
    search: jest.fn((q: { scope: string }) =>
      of(
        makeSearch({
          scope: q.scope as never,
          hits: q.scope === 'formats' ? [formatHit] : [makeHit()],
        }),
      ),
    ),
    ...over,
  };
}

async function setup(archive = fakeArchive(), url = '/dossiers', can: (p: string) => boolean = () => true) {
  const view = await render(CommandPaletteComponent, {
    providers: [
      provideRouter([]),
      { provide: ArchiveApi, useValue: archive },
      { provide: AuthService, useValue: fakeAuth({ can }) },
      {
        provide: NavService,
        useValue: { visible: () => NAV_ITEMS.filter((i) => i.key !== 'admin') },
      },
    ],
  });
  const router = TestBed.inject(Router);
  jest.spyOn(router, 'url', 'get').mockReturnValue(url);
  const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
  const navigateByUrl = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  return { view, archive, navigate, navigateByUrl, palette: TestBed.inject(PaletteService) };
}

async function open(palette: PaletteService, view: { fixture: { detectChanges(): void } }) {
  palette.show();
  view.fixture.detectChanges();
  return screen.findByRole('combobox', { name: 'Dossiers, Formate, Aktionen und Seiten suchen' });
}

describe('CommandPaletteComponent', () => {
  it('focuses the field when it opens and closes with Escape', async () => {
    const { palette, view } = await setup();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    const field = await open(palette, view);
    await waitFor(() => expect(field).toHaveFocus());
    await userEvent.keyboard('{Escape}');
    expect(palette.isOpen()).toBe(false);
  });

  it('shows Aktionen and Navigation without a term, filtered by the pages of the person', async () => {
    const { palette, view } = await setup();
    await open(palette, view);
    const list = screen.getByRole('listbox');
    expect(within(list).getByRole('group', { name: 'Aktionen' })).toBeInTheDocument();
    expect(within(list).getByRole('group', { name: 'Navigation' })).toBeInTheDocument();
    expect(within(list).getByRole('option', { name: 'Neues Event' })).toBeInTheDocument();
    expect(within(list).getByRole('option', { name: 'Archiv' })).toBeInTheDocument();
    expect(within(list).queryByRole('option', { name: 'Verwaltung' })).not.toBeInTheDocument();
    expect(
      within(list).queryByRole('option', { name: 'Als Format speichern' }),
    ).not.toBeInTheDocument();
  });

  it('offers "Als Format speichern" only inside a dossier and sends the command', async () => {
    const { palette, view } = await setup(fakeArchive(), '/dossiers/ev-1');
    TestBed.inject(DossierCommands).allowed.set(['clone', 'save-as-format']);
    await open(palette, view);
    await userEvent.click(screen.getByRole('option', { name: 'Als Format speichern' }));
    expect(TestBed.inject(DossierCommands).pending()?.name).toBe('save-as-format');
    expect(palette.isOpen()).toBe(false);
  });

  it('hides "Als Format speichern" when the open dossier does not allow it', async () => {
    const { palette, view } = await setup(fakeArchive(), '/dossiers/ev-1');
    TestBed.inject(DossierCommands).allowed.set(['clone']);
    await open(palette, view);
    expect(screen.queryByRole('option', { name: 'Als Format speichern' })).not.toBeInTheDocument();
  });

  it('lists no creating actions for a person without event.create', async () => {
    const { palette, view } = await setup(fakeArchive(), '/dossiers', (p) => p !== 'event.create');
    await open(palette, view);
    expect(screen.queryByRole('option', { name: 'Neues Event' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Neu aus Vorlage' })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Archiv' })).toBeInTheDocument();
  });

  it('says so when the search fails, and names the rate limit', async () => {
    const archive = fakeArchive({
      search: jest.fn(() => throwError(() => ({ status: 429 }))),
    });
    const { palette, view } = await setup(archive);
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    expect(await screen.findByRole('alert')).toHaveTextContent('Zu viele Suchen');
  });

  it('searches two groups in parallel 200 ms after the last key and groups the answers', async () => {
    const { palette, view, archive } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    await waitFor(() => expect(archive.search).toHaveBeenCalledTimes(2));
    expect(archive.search).toHaveBeenCalledWith({ q: 'movie', scope: 'events', limit: 5 });
    expect(archive.search).toHaveBeenCalledWith({ q: 'movie', scope: 'formats', limit: 3 });
    expect(await screen.findByRole('group', { name: 'Dossiers' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Formate' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/\d+ Ergebnisse/);
  });

  it('sends no request for one letter', async () => {
    const { palette, view, archive } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'm');
    await new Promise((r) => setTimeout(r, 300));
    expect(archive.search).not.toHaveBeenCalled();
  });

  it('drops a search that was still waiting when the palette closed', async () => {
    const { palette, view, archive } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'Archiv');
    palette.hide();
    view.fixture.detectChanges();
    await open(palette, view);
    await new Promise((r) => setTimeout(r, 300));
    expect(archive.search).not.toHaveBeenCalled();
    expect(screen.queryByRole('group', { name: 'Dossiers' })).not.toBeInTheDocument();
  });

  it('never lets an older answer replace a newer one', async () => {
    const slow = new Subject<SearchOut>();
    const search = jest.fn((q: { q: string; scope: string }) =>
      q.q === 'ab' && q.scope === 'events'
        ? slow
        : of(
            makeSearch({
              hits: q.scope === 'formats' ? [] : [makeHit({ id: 'new', title: 'Neu gefunden' })],
            }),
          ),
    );
    const { palette, view } = await setup(fakeArchive({ search }));
    const field = await open(palette, view);
    await userEvent.type(field, 'ab');
    await waitFor(() => expect(search).toHaveBeenCalledWith(expect.objectContaining({ q: 'ab' })));
    await userEvent.type(field, 'c');
    expect(await screen.findByRole('option', { name: /Neu gefunden/ })).toBeInTheDocument();
    slow.next(makeSearch({ hits: [makeHit({ id: 'old', title: 'Alt gefunden' })] }));
    slow.complete();
    view.fixture.detectChanges();
    expect(screen.queryByRole('option', { name: /Alt gefunden/ })).not.toBeInTheDocument();
  });

  it('survives a failed search and still offers the local entries', async () => {
    const { palette, view } = await setup(
      fakeArchive({ search: jest.fn(() => throwError(() => new Error('x'))) }),
    );
    const field = await open(palette, view);
    await userEvent.type(field, 'archiv');
    await waitFor(() => expect(screen.getByRole('option', { name: 'Archiv' })).toBeInTheDocument());
  });

  it('moves with the arrow keys through the options with aria-activedescendant and runs with Enter', async () => {
    const { palette, view, navigate } = await setup();
    const field = await open(palette, view);
    const first = screen.getAllByRole('option')[0];
    expect(field).toHaveAttribute('aria-activedescendant', first.id);
    expect(first).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowDown}');
    const second = screen.getAllByRole('option')[1];
    expect(field).toHaveAttribute('aria-activedescendant', second.id);
    await userEvent.keyboard('{ArrowUp}{ArrowUp}');
    expect(field).toHaveAttribute(
      'aria-activedescendant',
      screen.getAllByRole('option').at(-1)!.id,
    );
    await userEvent.keyboard('{Home}{Enter}');
    expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], undefined);
    expect(palette.isOpen()).toBe(false);
  });

  it('opens a hit: own dossier, archived dossier of another organization and format', async () => {
    const search = jest.fn((q: { scope: string }) =>
      of(
        makeSearch({
          hits:
            q.scope === 'formats'
              ? [formatHit]
              : [makeHit({ id: 'own' }), makeHit({ id: 'other', title: 'Fremd', foreign: true })],
        }),
      ),
    );
    const { palette, view, navigate, navigateByUrl } = await setup(fakeArchive({ search }));
    const field = await open(palette, view);
    await userEvent.type(field, 'xyz');
    await userEvent.click(await screen.findByRole('option', { name: /Fachschaftssitzung/ }));
    expect(navigate).toHaveBeenLastCalledWith(['/dossiers/own'], undefined);
    palette.show();
    view.fixture.detectChanges();
    await userEvent.type(await screen.findByRole('combobox'), 'xyz');
    await userEvent.click(await screen.findByRole('option', { name: /Fremd/ }));
    expect(navigate).toHaveBeenLastCalledWith(['/archiv/other'], undefined);
    palette.show();
    view.fixture.detectChanges();
    await userEvent.type(await screen.findByRole('combobox'), 'xyz');
    await userEvent.click(await screen.findByRole('option', { name: /Movienight/ }));
    expect(navigateByUrl).toHaveBeenCalledWith('/formate/movienight');
  });

  it('passes the mode "Aus Vorlage" to the new-event dialog', async () => {
    const { palette, view, navigate } = await setup();
    await open(palette, view);
    await userEvent.click(screen.getByRole('option', { name: 'Neu aus Vorlage' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], { queryParams: { modus: 'vorlage' } });
  });

  it('says so when nothing matches', async () => {
    const { palette, view } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'zzzzzz');
    await waitFor(() => expect(screen.getByText('Nichts gefunden.')).toBeInTheDocument());
  });

  it('keeps the focus inside the dialog with Tab', async () => {
    const { palette, view } = await setup();
    await open(palette, view);
    const dialog = screen.getByRole('dialog');
    for (let i = 0; i < 4; i++) {
      await userEvent.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it('has no axe violations', async () => {
    const { palette, view } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    await screen.findByRole('group', { name: 'Formate' });
    expect(await runAxe(document.body)).toHaveNoViolations();
  }, 30_000);

  it('jumps to the last option with End and highlights the one under the mouse', async () => {
    const { palette, view } = await setup();
    const field = await open(palette, view);
    await userEvent.keyboard('{End}');
    const options = screen.getAllByRole('option');
    expect(field).toHaveAttribute('aria-activedescendant', options.at(-1)!.id);
    await userEvent.hover(options[1]);
    expect(field).toHaveAttribute('aria-activedescendant', options[1].id);
  });

  it('shows the other group when one of the two searches fails', async () => {
    const search = jest.fn((q: { scope: string }) =>
      q.scope === 'events'
        ? throwError(() => new Error('x'))
        : of(makeSearch({ hits: [formatHit] })),
    );
    const { palette, view } = await setup(fakeArchive({ search }));
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    expect(await screen.findByRole('group', { name: 'Formate' })).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: 'Dossiers' })).not.toBeInTheDocument();
  });

  it('shows the dossiers when the format search fails', async () => {
    const search = jest.fn((q: { scope: string }) =>
      q.scope === 'formats' ? throwError(() => new Error('x')) : of(makeSearch()),
    );
    const { palette, view } = await setup(fakeArchive({ search }));
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    expect(await screen.findByRole('group', { name: 'Dossiers' })).toBeInTheDocument();
  });

  it('clears the hits again when the term gets shorter than two letters', async () => {
    const { palette, view } = await setup();
    const field = await open(palette, view);
    await userEvent.type(field, 'movie');
    await screen.findByRole('group', { name: 'Dossiers' });
    await userEvent.clear(field);
    await waitFor(() =>
      expect(screen.queryByRole('group', { name: 'Dossiers' })).not.toBeInTheDocument(),
    );
  });
});
