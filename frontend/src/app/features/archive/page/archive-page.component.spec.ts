import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { render, screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeHit, makeSearch } from '../../../../testing/m5-fixtures';
import { ArchiveApi } from '../api/archive-api.service';
import { ArchivePageComponent } from './archive-page.component';

const hitHeading = () =>
  screen.findByRole('article', { name: 'Fachschaftssitzung WS25/26' });

describe('ArchivePageComponent', () => {
  async function setup(query: Record<string, string | string[]> = {}, search = jest.fn(() => of(makeSearch()))) {
    const params = new BehaviorSubject(convertToParamMap(query));
    const view = await render(ArchivePageComponent, {
      providers: [
        provideRouter([]),
        { provide: ArchiveApi, useValue: { search } },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: params.value }, queryParamMap: params },
        },
      ],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    const router = TestBed.inject(Router);
    const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
    const navigateByUrl = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    return { view, search, navigate, navigateByUrl, params };
  }

  it('hints before there is a search term and sends no request', async () => {
    const { search } = await setup();
    expect(screen.getAllByText('Suche nach Titel, Ort, Anleitung …').length).toBeGreaterThan(0);
    expect(search).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { level: 1, name: 'Archiv' })).toBeInTheDocument();
  });

  it('searches the archive by default and shows hits with the count', async () => {
    const { search } = await setup({ q: 'sitzung' });
    expect(await hitHeading()).toBeInTheDocument();
    expect(search).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'sitzung', scope: 'events', state: ['archived'] }),
    );
    expect(screen.getByRole('status')).toHaveTextContent('1 Treffer');
  });

  it('searches live after a short delay and limits the input to 100 characters', async () => {
    const { search } = await setup();
    const field = screen.getByRole('searchbox', { name: 'Archiv durchsuchen' });
    expect(field).toHaveAttribute('maxlength', '100');
    await userEvent.type(field, 'kino');
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'kino' })));
  });

  it('switches the scope and drops the state filter for documents and formats', async () => {
    const { search } = await setup({ q: 'sitzung' });
    await hitHeading();
    await userEvent.click(screen.getByRole('radio', { name: 'Dokumente' }));
    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ scope: 'documents' })),
    );
    expect((search.mock.calls as unknown[][]).at(-1)?.[0]).not.toHaveProperty('state');
  });

  it('offers the suggestion when nothing is found and searches with it', async () => {
    const empty = jest.fn((query: { q: string }) =>
      of(makeSearch({ q: query.q, total: 0, hits: [], suggestion: query.q === 'kinabnd' ? 'Kinoabend' : null })),
    );
    const { search } = await setup({ q: 'kinabnd' }, empty as never);
    expect(await screen.findByText('Nichts gefunden für „kinabnd“.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '„Kinoabend“' }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'Kinoabend' })));
  });

  const failing = (status: number, code?: string) =>
    jest.fn(() => throwError(() => new HttpErrorResponse({ status, error: { status, code } })));

  it('says so when the search term is too long', async () => {
    await setup({ q: 'xx' }, failing(422, 'query_too_long') as never);
    expect(await screen.findByRole('alert')).toHaveTextContent('Suchbegriff zu lang (höchstens 100 Zeichen).');
  });

  it('says so when the search takes too long', async () => {
    await setup({ q: 'xx' }, failing(503, 'search_timeout') as never);
    expect(await screen.findByRole('alert')).toHaveTextContent('zu lange gedauert');
  });

  it('says so on any other error', async () => {
    await setup({ q: 'xx' }, failing(500) as never);
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Suche ist gerade nicht möglich.');
  });

  it('shows the facets with counts and sets a filter from one', async () => {
    const { search } = await setup({ q: 'sitzung' });
    await hitHeading();
    await userEvent.click(screen.getByRole('button', { name: /Organisation/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'FSI (1)' }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ org: 'fsi' })));
  });

  it('opens an own dossier, an archived dossier of another organization and a template', async () => {
    const search = jest.fn(() =>
      of(
        makeSearch({
          total: 2,
          hits: [makeHit({ id: 'own' }), makeHit({ id: 'other', title: 'Fremd', foreign: true })],
        }),
      ),
    );
    const { navigate } = await setup({ q: 'sitzung' }, search);
    await screen.findByText('Fremd');
    const buttons = screen.getAllByRole('button', { name: 'Öffnen' });
    await userEvent.click(buttons[0]);
    expect(navigate).toHaveBeenLastCalledWith(['/dossiers', 'own']);
    await userEvent.click(buttons[1]);
    expect(navigate).toHaveBeenLastCalledWith(['/archiv', 'other']);
    await userEvent.click(screen.getAllByRole('button', { name: 'Neu aus Vorlage' })[0]);
    expect(navigate).toHaveBeenLastCalledWith(['/dossiers/neu'], { queryParams: { vorlage: 'own' } });
  });

  it('follows the link of a document or format hit', async () => {
    const search = jest.fn(() =>
      of(makeSearch({ hits: [makeHit({ kind: 'format', id: 'movienight', link: '/formate/movienight' })] })),
    );
    const { navigateByUrl } = await setup({ q: 'movie', scope: 'formats' }, search);
    await userEvent.click(await screen.findByRole('button', { name: 'Öffnen' }));
    expect(navigateByUrl).toHaveBeenCalledWith('/formate/movienight');
  });

  it('loads more hits behind the first page', async () => {
    const first = makeSearch({ total: 2, hits: [makeHit({ id: 'a', title: 'Erste' })] });
    const second = makeSearch({ total: 2, hits: [makeHit({ id: 'b', title: 'Zweite' })] });
    const search = jest.fn().mockReturnValueOnce(of(first)).mockReturnValue(of(second));
    await setup({ q: 'sitzung' }, search as never);
    await userEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }));
    expect(await screen.findByText('Zweite')).toBeInTheDocument();
    expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 1 }));
    expect(screen.queryByRole('button', { name: 'Weitere laden' })).not.toBeInTheDocument();
  });

  it('resets the facets', async () => {
    const { search } = await setup({ q: 'sitzung', org: 'fsi' });
    await hitHeading();
    await userEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith(expect.objectContaining({ org: undefined })));
  });

  it('has no axe violations with hits', async () => {
    const { view } = await setup({ q: 'sitzung' });
    await hitHeading();
    const list = within(view.container as HTMLElement);
    expect(list.getAllByRole('article').length).toBe(1);
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('opens a document of another organization in the library', async () => {
    const search = jest.fn(() => of(makeSearch({ hits: [makeHit({ kind: 'document', id: 'd9', foreign: true })] })));
    const { navigate } = await setup({ q: 'sitzung', scope: 'documents' }, search);
    await userEvent.click(await screen.findByRole('button', { name: 'Öffnen' }));
    expect(navigate).toHaveBeenCalledWith(['/bibliothek', 'document', 'd9']);
  });

  it('keeps the list when loading more fails', async () => {
    const first = makeSearch({ total: 2, hits: [makeHit({ id: 'a' })] });
    const search = jest.fn().mockReturnValueOnce(of(first)).mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));
    await setup({ q: 'sitzung' }, search as never);
    await userEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }));
    expect(screen.getByRole('button', { name: 'Weitere laden' })).toBeEnabled();
    expect(screen.getAllByRole('article')).toHaveLength(1);
  });

  it('keeps a selected facet value that the answer does not list', async () => {
    await setup({ q: 'sitzung', org: 'zzz' });
    await hitHeading();
    await userEvent.click(screen.getByRole('button', { name: /Organisation/ }));
    expect(await screen.findByRole('option', { name: 'zzz' })).toBeInTheDocument();
  });
});
