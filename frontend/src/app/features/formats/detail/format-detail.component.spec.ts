import { HttpErrorResponse } from '@angular/common/http';
import { DeferBlockBehavior, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, fakeAuth } from '../../../../testing/event-fixtures';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { DocumentsApi } from '../../dossiers/api/documents-api.service';
import { EventsApi } from '../../dossiers/api/events-api.service';
import { FormatsApi } from '../api/formats-api.service';
import type { FormatOut } from '../model/format.models';
import { FormatDetailComponent } from './format-detail.component';

const master = {
  id: 'doc-1', kind: 'howto', title: 'Anleitung', visibility: 'shared', carryOver: true, rev: 2,
  verifiedAt: null, verifiedBy: null, updatedAt: '2026-10-01T10:00:00Z', bodyMd: '## Vorher',
};

function fakeFormats(format: FormatOut = makeFormat(), over: Record<string, unknown> = {}) {
  return {
    get: jest.fn(() => of(format)),
    verify: jest.fn(() => of(format)),
    createHowto: jest.fn(() => of(format)),
    newEdition: jest.fn(() => of({ event: { id: 'n1' }, report: [] })),
    ...over,
  };
}

async function setup(formats = fakeFormats(), can: string[] = ['format.manage']) {
  const view = await render(FormatDetailComponent, {
    inputs: { slug: 'movienight' },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      provideRouter([]),
      { provide: FormatsApi, useValue: formats },
      { provide: EventsApi, useValue: fakeApi() },
      { provide: AuthService, useValue: fakeAuth({ can: (p: string) => can.includes(p) }) },
      {
        provide: DocumentsApi,
        useValue: {
          get: jest.fn(() => of(master)),
          getDraft: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))),
          putDraft: jest.fn(() => of({})),
          put: jest.fn(() => of(master)),
          deleteDraft: jest.fn(() => of(undefined)),
        },
      },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const router = TestBed.inject(Router);
  return {
    view,
    formats,
    navigate: jest.spyOn(router, 'navigate').mockResolvedValue(true),
  };
}

describe('FormatDetailComponent', () => {
  afterEach(() => localStorage.clear());

  it('shows name, organization, description, the master howto and "Zuletzt geprüft"', async () => {
    await setup();
    expect(await screen.findByRole('heading', { name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText('Kino im Hörsaal.')).toBeInTheDocument();
    expect(screen.getByText(/Zuletzt geprüft von Mara Keller am/)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Master-Anleitung' })).toHaveValue('## Vorher');
    expect(screen.getByText(/Bitte keine privaten Telefonnummern/)).toBeInTheDocument();
  });

  it('shows the last edition with attendance and costs', async () => {
    await setup();
    const card = (await screen.findByRole('heading', { name: 'Letzte Ausgabe' })).closest('section') as HTMLElement;
    expect(card).toHaveTextContent('Movienight SoSe26');
    expect(card).toHaveTextContent('87');
    expect(card).toHaveTextContent('245,00');
  });

  it('warns in text when the howto is older than twelve months', async () => {
    await setup(fakeFormats(makeFormat({ howtoStale: true })));
    expect(await screen.findByText('Anleitung seit über 12 Monaten ungeprüft')).toBeInTheDocument();
  });

  it('marks the howto as verified and reloads', async () => {
    const { formats } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Als geprüft markieren' }));
    expect(formats.verify).toHaveBeenCalledWith('movienight');
    expect(formats.get).toHaveBeenCalledTimes(2);
  });

  it('is read only without the right: no verify button, no save button', async () => {
    await setup(fakeFormats(), []);
    await screen.findByRole('heading', { name: 'Movienight' });
    expect(screen.queryByRole('button', { name: 'Als geprüft markieren' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Als neue Fassung speichern' })).not.toBeInTheDocument();
  });

  it('lets a submitter of the organization manage the format', async () => {
    await setup(fakeFormats(), ['event.submit']);
    expect(await screen.findByRole('button', { name: 'Als geprüft markieren' })).toBeInTheDocument();
  });

  it('offers to create the master howto when there is none, also from the last edition', async () => {
    const { formats } = await setup(fakeFormats(makeFormat({ masterHowto: null, howtoStale: true })));
    expect(await screen.findByText('Noch keine Master-Anleitung.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Anleitung anlegen' }));
    expect(formats.createHowto).toHaveBeenCalledWith('movienight', undefined);
    await userEvent.click(screen.getByRole('button', { name: 'Aus der letzten Ausgabe übernehmen' }));
    expect(formats.createHowto).toHaveBeenLastCalledWith('movienight', 'ed-2');
  });

  it('lists the editions in the tab Ausgaben and opens one', async () => {
    const { navigate } = await setup();
    await userEvent.click(await screen.findByRole('tab', { name: /Ausgaben/ }));
    await userEvent.click(screen.getByText('Movienight WS25/26', { exact: false }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'ed-1']);
  });

  it('opens the archive page for an edition of another organization', async () => {
    const format = makeFormat();
    format.editions[0] = { ...format.editions[0], foreign: true, costsCents: null };
    const { navigate } = await setup(fakeFormats(format));
    await userEvent.click(await screen.findByRole('tab', { name: /Ausgaben/ }));
    await userEvent.click(screen.getByText('Movienight WS25/26', { exact: false }));
    expect(navigate).toHaveBeenCalledWith(['/archiv', 'ed-1']);
  });

  it('shows the empty state of the editions with a button', async () => {
    await setup(fakeFormats(makeFormat({ editions: [], lastEdition: null })));
    await userEvent.click(await screen.findByRole('tab', { name: /Ausgaben/ }));
    expect(screen.getByText('Noch keine Ausgabe dieses Formats.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neue Ausgabe' }).at(-1)!);
    expect(await screen.findByRole('dialog', { name: 'Neue Ausgabe: Movienight' })).toBeInTheDocument();
  });

  it('shows the checklist of the profile and the mail templates, read only', async () => {
    await setup();
    await userEvent.click(await screen.findByRole('tab', { name: 'Checkliste und Mails' }));
    expect(screen.getByText('Raum buchen')).toBeInTheDocument();
    expect(screen.getByText('Pflicht')).toBeInTheDocument();
    expect(screen.getByText('Einladung')).toBeInTheDocument();
  });

  it('starts the clone dialog with the format for a format with editions', async () => {
    const { navigate } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Neue Ausgabe' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], { queryParams: { format: 'movienight' } });
  });

  it('opens the small dialog for a format without editions', async () => {
    await setup(fakeFormats(makeFormat({ editions: [], lastEdition: null })));
    await userEvent.click(await screen.findByRole('button', { name: 'Neue Ausgabe' }));
    expect(await screen.findByRole('dialog', { name: 'Neue Ausgabe: Movienight' })).toBeInTheDocument();
  });

  it('shows an error note with a retry when the format does not load', async () => {
    const formats = fakeFormats();
    formats.get.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 500 })));
    await setup(formats);
    expect(await screen.findByRole('alert')).toHaveTextContent('Das Format konnte nicht geladen werden.');
    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
    expect(await screen.findByRole('heading', { name: 'Movienight' })).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    await screen.findByRole('heading', { name: 'Movienight' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  }, 30_000);

  it('opens the new dossier after the small dialog planned the edition', async () => {
    const { navigate } = await setup(fakeFormats(makeFormat({ editions: [], lastEdition: null })));
    await userEvent.click(await screen.findByRole('button', { name: 'Neue Ausgabe' }));
    await userEvent.type(await screen.findByLabelText(/Beginn, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:30');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'n1']);
  });

  it('keeps the page and shows a toast when the verification is refused', async () => {
    const formats = fakeFormats(makeFormat(), {
      verify: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    });
    await setup(formats);
    await userEvent.click(await screen.findByRole('button', { name: 'Als geprüft markieren' }));
    expect(formats.get).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Als geprüft markieren' })).toBeEnabled();
  });
});
