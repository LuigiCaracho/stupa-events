import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi } from '../../../../testing/event-fixtures';
import { makeLibraryItem } from '../../../../testing/m5-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { LibraryApi } from '../api/library-api.service';
import { LibraryDetailComponent } from './library-detail.component';

const doc = { id: 'doc-7', kind: 'howto', title: 'Anleitung Hüttencafé', visibility: 'shared', carryOver: true, rev: 1, verifiedAt: null as string | null, verifiedBy: null, updatedAt: '', bodyMd: 'Erst **Kaffee** kochen' };

async function setup(inputs: Record<string, unknown>, document = jest.fn(() => of(doc))) {
  const view = await render(LibraryDetailComponent, {
    inputs,
    providers: [
      provideRouter([]),
      { provide: LibraryApi, useValue: { document, downloadUrl: (id: string) => `/d/${id}`, previewUrl: (id: string) => `/p/${id}`, adopt: jest.fn() } },
      { provide: EventsApi, useValue: fakeApi() },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, document };
}

describe('LibraryDetailComponent', () => {
  it('shows a document rendered, with its source and the warning when it is unchecked', async () => {
    await setup({ kind: 'document', id: 'doc-7', item: makeLibraryItem() });
    expect(await screen.findByRole('heading', { level: 2, name: 'Anleitung Hüttencafé' })).toBeInTheDocument();
    expect(screen.getByText('Kaffee', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Hüttencafé 2025' })).toHaveAttribute('href', '/archiv/ev-3');
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('links a source of the own organization to the dossier and a format source to the format', async () => {
    const own = makeLibraryItem({ source: { ...makeLibraryItem().source, own: true } });
    const view = await setup({ kind: 'document', id: 'doc-7', item: own });
    expect(await screen.findByRole('link', { name: 'Hüttencafé 2025' })).toHaveAttribute('href', '/dossiers/ev-3');
    view.view.fixture.componentRef.setInput('item', makeLibraryItem({ source: { ...makeLibraryItem().source, type: 'format', id: 'movienight', title: 'Movienight' } }));
    view.view.fixture.detectChanges();
    expect(screen.getByRole('link', { name: 'Movienight' })).toHaveAttribute('href', '/formate/movienight');
  });

  it('shows the review date of a checked document', async () => {
    await setup({ kind: 'document', id: 'doc-7', item: null }, jest.fn(() => of({ ...doc, verifiedAt: '2026-02-12T10:00:00Z' })));
    expect(await screen.findByText('Anleitung geprüft am 12.02.2026')).toBeInTheDocument();
  });

  it('opens the adopt dialog', async () => {
    await setup({ kind: 'document', id: 'doc-7', item: null });
    await userEvent.click(await screen.findByRole('button', { name: 'In Dossier übernehmen' }));
    expect(await screen.findByRole('dialog', { name: 'In Dossier übernehmen' })).toBeInTheDocument();
  });

  it('answers 404 with the not-found note and any other error with the load error', async () => {
    const missing = await setup({ kind: 'document', id: 'x', item: null }, jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404, error: { status: 404 } }))));
    expect(await screen.findByRole('alert')).toHaveTextContent('nicht geteilt');
    missing.view.fixture.destroy();
  });

  it('shows the load error for a failing document', async () => {
    await setup({ kind: 'document', id: 'x', item: null }, jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Bibliothek konnte nicht geladen werden.');
  });

  it('shows a file with name, type, size, preview of an image and the download', async () => {
    const item = makeLibraryItem({ kind: 'attachment', id: 'att-1', title: 'plakat.png', mime: 'image/png', sizeBytes: 3_145_728, subKind: 'poster' });
    await setup({ kind: 'attachment', id: 'att-1', item });
    expect(screen.getByRole('heading', { level: 2, name: 'plakat.png' })).toBeInTheDocument();
    expect(screen.getByText('image/png')).toBeInTheDocument();
    expect(screen.getByText('3,0 MB')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Herunterladen' })).toHaveAttribute('href', '/d/att-1');
    expect(document.querySelector('app-image-thumb')).not.toBeNull();
  });

  it('shows a file without a list row (deep link) with only the download', async () => {
    await setup({ kind: 'attachment', id: 'att-2', item: null });
    expect(screen.getByRole('heading', { level: 2, name: 'Datei' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Herunterladen' })).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup({ kind: 'document', id: 'doc-7', item: makeLibraryItem() });
    await screen.findByRole('heading', { level: 2, name: 'Anleitung Hüttencafé' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
