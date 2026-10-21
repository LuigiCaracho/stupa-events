/** The sections "So lief es" and Rahmen of the dossier page, the location dialog and the outcome that comes back. */
import { of } from 'rxjs';
import { TestBed } from '@angular/core/testing';
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { DocumentsApi } from '../api/documents-api.service';
import type { EventDto } from '../api/event.models';
import { can, setup } from '../../../../testing/dossier-detail-harness';

const archived = (over: Partial<EventDto> = {}): EventDto =>
  makeEvent({
    state: 'archived',
    editableFields: [],
    allowedActions: ['verify-howto', 'save-as-format'],
    ...over,
  });

describe('DossierDetailComponent sections', () => {
  afterEach(() => localStorage.clear());

  it('writes "So lief es" in the archive: retrospective, result and the tick for the howto', async () => {
    await setup(fakeApi({ get: jest.fn(() => of(archived())) }), can('event.edit'));
    expect(screen.getByRole('heading', { level: 2, name: 'So lief es' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Rückblick' })).toBeInTheDocument();
    expect(screen.getByLabelText('Besucher:innen')).toBeEnabled();
    expect(screen.getByRole('checkbox', { name: 'Anleitung geprüft' })).toBeEnabled();
  });

  it('takes the dossier that the result form returns', async () => {
    const { http } = await setup(fakeApi({ get: jest.fn(() => of(archived())) }), can('event.edit'));
    await userEvent.type(screen.getByLabelText('Besucher:innen'), '12');
    await userEvent.type(screen.getByLabelText(/Kosten \(Ist\)/), '5');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    const req = http.expectOne('/api/events/ev-1/outcome');
    expect(req.request.headers.get('If-Match')).toBe('"3"');
    req.flush(archived({ rev: 4, title: 'Movienight 2' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Movienight 2' })).toBeInTheDocument();
  });

  it('reloads the dossier after the retrospective was created', async () => {
    const { api } = await setup(fakeApi({ get: jest.fn(() => of(archived())) }), can('event.edit'));
    const before = api.get.mock.calls.length;
    const docs = TestBed.inject(DocumentsApi) as unknown as { create: jest.Mock };
    docs.create.mockReturnValue(
      of({ id: 'r1', kind: 'retrospective', title: 'Rückblick', visibility: 'org', carryOver: false, rev: 1, verifiedAt: null, verifiedBy: null, updatedAt: '' }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Rückblick speichern' }));
    expect(docs.create).toHaveBeenCalled();
    await new Promise((r) => setTimeout(r));
    expect(api.get.mock.calls.length).toBeGreaterThan(before);
  });

  it('confirms the place from the dialog and takes the answer', async () => {
    const { http } = await setup(
      fakeApi({
        get: jest.fn(() =>
          of(makeEvent({ state: 'published', allowedActions: ['confirm-location'], venueText: 'Kinosaal 9-133' })),
        ),
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Ort bestätigen' }));
    expect(screen.getByText('Der Ort ist öffentlich. Keine Privatadresse.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Ort bestätigen' }).at(-1)!);
    const req = http.expectOne('/api/events/ev-1/actions/confirm-location');
    expect(req.request.body).toEqual({ precision: 'building' });
    req.flush(makeEvent({ rev: 4, locationPrecision: 'building' }));
  });

  it('shows the facts block of the profile in Eckdaten', async () => {
    await setup(
      fakeApi({
        get: jest.fn(() =>
          of(makeEvent({ primaryCategory: { id: 'c', slug: 'p', name: 'Party', kind: 'format', requiredProfile: 'party' } })),
        ),
      }),
    );
    expect(screen.getByRole('heading', { name: 'Rahmen' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /Altersgrenze/ })).toBeInTheDocument();
  });

  it('warns "Anleitung ungeprüft" in the head of an archived dossier and not once it is checked', async () => {
    await setup(fakeApi({ get: jest.fn(() => of(archived({ howtoUnverified: true }))) }));
    expect(await screen.findByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('shows no warning once the howto is checked', async () => {
    await setup(fakeApi({ get: jest.fn(() => of(archived({ howtoVerifiedAt: '2026-10-01T10:00:00Z' }))) }));
    await new Promise((r) => setTimeout(r));
    expect(screen.queryByText('Anleitung ungeprüft')).not.toBeInTheDocument();
  });

  it('shows the format of the dossier as a link in the head', async () => {
    await setup(
      fakeApi({ get: jest.fn(() => of(archived({ format: { slug: 'movienight', title: 'Movienight' } }))) }),
    );
    expect(screen.getByRole('link', { name: 'Movienight' })).toHaveAttribute('href', '/formate/movienight');
  });
});
