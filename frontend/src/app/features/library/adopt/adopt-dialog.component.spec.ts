import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { fakeApi, makeCard } from '../../../../testing/event-fixtures';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { LibraryApi } from '../api/library-api.service';
import { AdoptDialogComponent } from './adopt-dialog.component';

async function setup(adopt = jest.fn(() => of({})), cards = [makeCard({ id: 'ev-1', title: 'Movienight' })]) {
  const closed = jest.fn();
  const api = fakeApi({ listCards: jest.fn(() => of({ items: cards, total: cards.length, limit: 100, offset: 0 })) });
  const view = await render(AdoptDialogComponent, {
    inputs: { documentId: 'doc-7', title: 'Anleitung Hüttencafé' },
    providers: [provideRouter([]), { provide: LibraryApi, useValue: { adopt } }, { provide: EventsApi, useValue: api }],
    on: { closed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, adopt, closed, api, navigate: jest.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true) };
}

describe('AdoptDialogComponent', () => {
  it('asks for your open dossiers only', async () => {
    const { api } = await setup();
    expect(api.listCards).toHaveBeenCalledWith(
      expect.objectContaining({ mine: true, state: ['idea', 'planning', 'in_review', 'approved', 'live', 'followup'] }),
    );
    expect(screen.getByRole('dialog', { name: 'In Dossier übernehmen' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Übernehmen' })).toBeDisabled();
  });

  it('adopts into the chosen dossier and opens it', async () => {
    const { adopt, closed, navigate } = await setup();
    await userEvent.click(screen.getByRole('combobox', { name: /Dossier/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Movienight' }));
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(adopt).toHaveBeenCalledWith('doc-7', 'ev-1');
    expect(closed).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'ev-1']);
  });

  it('says so when there is no open dossier', async () => {
    await setup(undefined, []);
    expect(await screen.findByText(/kein offenes Dossier/)).toBeInTheDocument();
  });

  it('reports a refusal', async () => {
    const { closed } = await setup(
      jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    );
    await userEvent.click(screen.getByRole('combobox', { name: /Dossier/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Movienight' }));
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(closed).not.toHaveBeenCalled();
    expect(TestBed.inject(ToastService).toasts().length).toBe(1);
  });
});
