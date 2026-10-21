import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi } from '../../../../testing/event-fixtures';
import { makeLibraryItem } from '../../../../testing/m5-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { LibraryApi } from '../api/library-api.service';
import type { LibraryPage } from '../model/library.models';
import { LibraryPageComponent } from './library-page.component';

const page = (over: Partial<LibraryPage> = {}): LibraryPage => ({
  items: [makeLibraryItem(), makeLibraryItem({ kind: 'attachment', id: 'att-1', title: 'ablauf.pdf', subKind: 'howto_file', mime: 'application/pdf', sizeBytes: 1024 })],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    category: [{ value: 'cafe', label: 'Café', count: 1 }],
    organization: [{ value: 'makers', label: 'MAKERS', count: 2 }],
    year: [{ value: '2025', label: '2025', count: 2 }],
    kind: [{ value: 'document', label: 'document', count: 1 }],
  },
  ...over,
});

async function setup(list = jest.fn(() => of(page())), query: Record<string, string> = {}, route: Record<string, string> = {}) {
  const params = new BehaviorSubject(convertToParamMap(query));
  const paramMap = new BehaviorSubject(convertToParamMap(route));
  const doc = { id: 'doc-7', kind: 'howto', title: 'Anleitung Hüttencafé', visibility: 'shared', carryOver: true, rev: 1, verifiedAt: null, verifiedBy: null, updatedAt: '', bodyMd: 'Text' };
  const view = await render(LibraryPageComponent, {
    providers: [
      provideRouter([]),
      { provide: LibraryApi, useValue: { list, document: jest.fn(() => of(doc)), downloadUrl: (id: string) => `/api/attachments/${id}/download`, previewUrl: (id: string) => `/p/${id}` } },
      { provide: EventsApi, useValue: fakeApi() },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: params.value, paramMap: paramMap.value }, queryParamMap: params, paramMap },
      },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const router = TestBed.inject(Router);
  return { view, list, navigate: jest.spyOn(router, 'navigate').mockResolvedValue(true) };
}

describe('LibraryPageComponent', () => {
  it('lists documents and files with their kind, organization and year', async () => {
    await setup();
    expect(await screen.findByRole('link', { name: 'Anleitung Hüttencafé' })).toHaveAttribute('href', '/bibliothek/document/doc-7');
    expect(screen.getByRole('link', { name: 'ablauf.pdf' })).toHaveAttribute('href', '/bibliothek/attachment/att-1');
    expect(screen.getByText('Anleitung · MAKERS · 2025')).toBeInTheDocument();
    expect(screen.getByText('2 Einträge')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Bibliothek' })).toBeInTheDocument();
  });

  it('says what the library is for when it is empty', async () => {
    await setup(jest.fn(() => of(page({ items: [], total: 0 }))));
    expect(
      await screen.findByText('Die Bibliothek ist leer. Gute Anleitungen aus Dossiers lassen sich hierher übernehmen.'),
    ).toBeInTheDocument();
  });

  it('says so when the filters match nothing', async () => {
    await setup(jest.fn(() => of(page({ items: [], total: 0 }))), { q: 'zzz' });
    expect(await screen.findByText('Nichts gefunden. Versuch es mit weniger Filtern.')).toBeInTheDocument();
  });

  it('shows an error note when the list does not load', async () => {
    await setup(jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Bibliothek konnte nicht geladen werden.');
  });

  it('searches live and filters by a facet with its count', async () => {
    const { list } = await setup();
    await screen.findByRole('link', { name: 'ablauf.pdf' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Bibliothek durchsuchen' }), 'cafe');
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'cafe' })));
    await userEvent.click(screen.getByRole('button', { name: /Organisation/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'MAKERS (2)' }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ organization: 'makers' })));
  });

  it('labels the kind facet in German', async () => {
    await setup();
    await screen.findByRole('link', { name: 'ablauf.pdf' });
    await userEvent.click(screen.getByRole('button', { name: /Art/ }));
    expect(await screen.findByRole('option', { name: 'Dokumente (1)' })).toBeInTheDocument();
  });

  it('loads more items behind the first page', async () => {
    const list = jest.fn().mockReturnValueOnce(of(page({ total: 3 }))).mockReturnValue(of(page({ total: 3, items: [makeLibraryItem({ id: 'doc-8', title: 'Dritte' })] })));
    await setup(list as never);
    await userEvent.click(await screen.findByRole('button', { name: 'Weitere laden' }));
    expect(await screen.findByRole('link', { name: 'Dritte' })).toBeInTheDocument();
    expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 2 }));
  });

  it('shows the open document beside the list', async () => {
    await setup(undefined, {}, { kind: 'document', id: 'doc-7' });
    expect(await screen.findByRole('heading', { level: 2, name: 'Anleitung Hüttencafé' })).toBeInTheDocument();
    expect(screen.getByText('Text')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'In Dossier übernehmen' })).toBeInTheDocument();
  });

  it('shows an open file with its download link', async () => {
    await setup(undefined, {}, { kind: 'attachment', id: 'att-1' });
    const link = await screen.findByRole('link', { name: 'Herunterladen' });
    expect(link).toHaveAttribute('href', '/api/attachments/att-1/download');
  });

  it('resets the filters', async () => {
    const { list } = await setup(undefined, { org: 'makers' });
    await userEvent.click(await screen.findByRole('button', { name: 'Filter zurücksetzen' }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ organization: undefined })));
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('link', { name: 'ablauf.pdf' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('goes back to the list and keeps the filters when the open item is closed', async () => {
    const { view, navigate } = await setup(undefined, {}, { kind: 'document', id: 'doc-7' });
    (view.fixture.componentInstance as unknown as { closeDetail(): void }).closeDetail();
    expect(navigate).toHaveBeenCalledWith(['/bibliothek'], { queryParamsHandling: 'preserve' });
  });

  it('shows a kind and a sub kind that have no German name as they are', async () => {
    const odd = page({
      items: [makeLibraryItem({ subKind: 'mystery' })],
      total: 1,
      facets: { category: [], organization: [], year: [], kind: [{ value: 'strange', label: 'Seltsam', count: 1 }] },
    });
    await setup(jest.fn(() => of(odd)));
    expect(await screen.findByText(/^mystery · MAKERS · 2025$/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Art/ }));
    expect(await screen.findByRole('option', { name: 'Seltsam (1)' })).toBeInTheDocument();
  });
});
