import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { FormatsApi } from '../api/formats-api.service';
import type { FormatCard } from '../model/format.models';
import { FormatListComponent } from './format-list.component';

const card = (over: Partial<FormatCard> = {}): FormatCard => ({
  slug: 'movienight',
  title: 'Movienight',
  organization: { slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
  active: true,
  lastVerifiedAt: '2026-02-12T10:00:00Z',
  howtoStale: false,
  editions: 23,
  lastEdition: null,
  ...over,
});

async function setup(list = jest.fn(() => of({ items: [card(), card({ slug: 'campusfest', title: 'Campusfest', howtoStale: true, lastVerifiedAt: null, editions: 2 })], total: 2, limit: 100, offset: 0 })), child: string | null = null) {
  const view = await render(FormatListComponent, {
    providers: [
      provideRouter([]),
      { provide: FormatsApi, useValue: { list, get: jest.fn(() => of(makeFormat())) } },
      {
        provide: ActivatedRoute,
        useValue: { firstChild: child ? { snapshot: { paramMap: new Map([['slug', child]]) } } : null },
      },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, list };
}

describe('FormatListComponent', () => {
  it('lists the formats with organization, editions and the review state of the howto', async () => {
    await setup();
    expect(await screen.findByRole('link', { name: 'Movienight' })).toHaveAttribute('href', '/formate/movienight');
    expect(screen.getByText('FSI · 23 Ausgaben')).toBeInTheDocument();
    expect(screen.getByText('Anleitung geprüft am 12.02.2026')).toBeInTheDocument();
    expect(screen.getByText('Anleitung seit über 12 Monaten ungeprüft')).toBeInTheDocument();
    expect(screen.getByText('2 Formate')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Formate' })).toBeInTheDocument();
  });

  it('searches live after a short delay', async () => {
    const { list } = await setup();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Formate suchen' }), 'camp');
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'camp' })));
  });

  it('says so when there are no formats and when loading fails', async () => {
    await setup(jest.fn(() => of({ items: [], total: 0, limit: 100, offset: 0 })));
    expect(await screen.findByText('Keine Formate gefunden.')).toBeInTheDocument();
  });

  it('shows an error note when the list does not load', async () => {
    await setup(jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))));
    expect(await screen.findByRole('alert')).toHaveTextContent('Das Format konnte nicht geladen werden.');
  });

  it('turns the heading into plain text while a format is open', async () => {
    const { view } = await setup(undefined, 'movienight');
    expect(view.container.querySelectorAll('h1')).toHaveLength(0);
    expect(view.container.querySelector('p.ph__title')).toHaveTextContent('Formate');
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('link', { name: 'Movienight' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('goes back to the plain list when the open format is closed', async () => {
    const { view } = await setup(undefined, 'movienight');
    const { Router } = await import('@angular/router');
    const { TestBed } = await import('@angular/core/testing');
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    (view.fixture.componentInstance as unknown as { closeDetail(): void }).closeDetail();
    expect(navigate).toHaveBeenCalledWith(['/formate']);
  });
});
