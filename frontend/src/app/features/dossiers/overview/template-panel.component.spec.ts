import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import type { ArchiveEventOut } from '../../archive/model/archive.models';
import { LibraryApi } from '../../library/api/library-api.service';
import { TemplatePanelComponent } from './template-panel.component';

const source = (over: Partial<ArchiveEventOut> = {}): ArchiveEventOut => ({
  id: 'tpl-1', title: 'Movienight SoSe26', summary: null, descriptionMd: null, state: 'archived',
  startsAt: '2026-06-02T17:00:00Z', endsAt: '2026-06-02T19:00:00Z',
  allDay: false, organization: { slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' }, category: null, format: null, venueName: null, attendance: null,
  documents: [{ id: 'd1', title: 'Anleitung', kind: 'howto', verifiedAt: null }],
  attachments: [{ id: 'a1', displayName: 'ablauf.pdf', kind: 'howto_file', mime: 'application/pdf', sizeBytes: 100 }],
  own: true, ...over,
});

async function setup(event = makeEvent({ derivedFromId: 'tpl-1' }), eventCall = jest.fn(() => of(source()))) {
  const view = await render(TemplatePanelComponent, {
    inputs: { event },
    providers: [
      provideRouter([]),
      { provide: ArchiveApi, useValue: { event: eventCall } },
      { provide: LibraryApi, useValue: { downloadUrl: (id: string) => `/api/attachments/${id}/download` } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, eventCall };
}

describe('TemplatePanelComponent', () => {
  it('links the template and lists what it shared', async () => {
    await setup();
    expect(await screen.findByRole('heading', { name: 'Aus der Vorlage' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Movienight SoSe26' })).toHaveAttribute('href', '/dossiers/tpl-1');
    expect(screen.getByRole('link', { name: 'Anleitung' })).toHaveAttribute('href', '/bibliothek/document/d1');
    expect(screen.getByRole('link', { name: 'ablauf.pdf' })).toHaveAttribute('href', '/api/attachments/a1/download');
  });

  it('links a template of another organization to the archive page', async () => {
    await setup(undefined, jest.fn(() => of(source({ own: false }))));
    expect(await screen.findByRole('link', { name: 'Movienight SoSe26' })).toHaveAttribute('href', '/archiv/tpl-1');
  });

  it('says nothing was shared when it is empty', async () => {
    await setup(undefined, jest.fn(() => of(source({ documents: [], attachments: [] }))));
    expect(await screen.findByText('Nichts geteilt.')).toBeInTheDocument();
  });

  it('shows no panel without a template and none when the source is gone', async () => {
    const { eventCall } = await setup(makeEvent());
    expect(eventCall).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: 'Aus der Vorlage' })).not.toBeInTheDocument();
  });

  it('shows no panel when the template is not readable any more', async () => {
    await setup(undefined, jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))));
    expect(screen.queryByRole('heading', { name: 'Aus der Vorlage' })).not.toBeInTheDocument();
  });
});
