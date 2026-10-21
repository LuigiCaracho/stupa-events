import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { LibraryApi } from '../../library/api/library-api.service';
import { ArchiveApi } from '../api/archive-api.service';
import type { ArchiveEventOut } from '../model/archive.models';
import { ArchiveEventComponent } from './archive-event.component';

const out: ArchiveEventOut = {
  id: 'ev-5',
  title: 'Movienight SoSe26',
  summary: 'Kino im Hörsaal',
  descriptionMd: 'Ein **Film**.',
  state: 'archived',
  startsAt: '2026-06-02T17:00:00Z',
  endsAt: '2026-06-02T19:30:00Z',
  allDay: false,
  organization: { slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
  category: { slug: 'kino', name: 'Kino' },
  format: { slug: 'movienight', title: 'Movienight' },
  venueName: 'Hörsaal 9-133',
  attendance: 87,
  documents: [{ id: 'd1', title: 'Anleitung', kind: 'howto', verifiedAt: null }],
  attachments: [{ id: 'a1', displayName: 'ablauf.pdf', kind: 'howto_file', mime: 'application/pdf', sizeBytes: 2_097_152 }],
  own: false,
};

async function setup(event = jest.fn(() => of(out))) {
  const view = await render(ArchiveEventComponent, {
    inputs: { id: 'ev-5' },
    providers: [
      provideRouter([]),
      { provide: ArchiveApi, useValue: { event } },
      { provide: LibraryApi, useValue: { downloadUrl: (id: string) => `/api/attachments/${id}/download` } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, event };
}

describe('ArchiveEventComponent', () => {
  it('shows the core data, attendance, the shared documents and files', async () => {
    await setup();
    expect(await screen.findByRole('heading', { level: 1, name: 'Movienight SoSe26' })).toBeInTheDocument();
    expect(screen.getByText('87 Besucher:innen')).toBeInTheDocument();
    expect(screen.getByText('Hörsaal 9-133')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Movienight' })).toHaveAttribute('href', '/formate/movienight');
    expect(screen.getByRole('link', { name: 'Anleitung' })).toHaveAttribute('href', '/bibliothek/document/d1');
    expect(screen.getByRole('link', { name: 'ablauf.pdf' })).toHaveAttribute('href', '/api/attachments/a1/download');
    expect(screen.getByText('2,0 MB')).toBeInTheDocument();
    expect(screen.getByText(/gehört einer anderen Organisation/)).toBeInTheDocument();
  });

  it('starts a new edition from it', async () => {
    await setup();
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    await userEvent.click(await screen.findByRole('button', { name: 'Neu aus Vorlage' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], { queryParams: { vorlage: 'ev-5' } });
  });

  it('says nothing is shared when nothing is', async () => {
    await setup(jest.fn(() => of({ ...out, documents: [], attachments: [] })));
    expect(await screen.findAllByText('Nichts geteilt.')).toHaveLength(2);
  });

  it('answers 404 with the not-found note and a way back', async () => {
    await setup(jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404, error: { status: 404 } }))));
    expect(await screen.findByRole('alert')).toHaveTextContent('nicht freigegeben');
    expect(screen.getByRole('link', { name: 'Zurück zum Archiv' })).toHaveAttribute('href', '/archiv');
  });

  it('offers a retry on any other error', async () => {
    const event = jest.fn().mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 500 }))).mockReturnValue(of(out));
    await setup(event);
    await userEvent.click(await screen.findByRole('button', { name: 'Erneut versuchen' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Movienight SoSe26' })).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('heading', { level: 1, name: 'Movienight SoSe26' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
