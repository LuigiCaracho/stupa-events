import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen, waitFor, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import { makeLastTime, makePreview, makeTemplate } from '../../../../testing/m5-fixtures';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { FormatsApi } from '../../formats/api/formats-api.service';
import { AttachmentsApi } from '../api/attachments-api.service';
import { EventsApi } from '../api/events-api.service';
import { CloneDialogComponent } from './clone-dialog.component';

const otherOrg = makeTemplate({
  id: 'tpl-2',
  attendance: null,
  title: 'Campusfest 2025',
  format: null,
  foreign: true,
  organization: { slug: 'makers', name: 'MAKERS', short: 'MKR' },
  howtoVerifiedAt: null,
  howtoUnverified: true,
});

function fakeArchive(over: Record<string, unknown> = {}) {
  return {
    templates: jest.fn(() =>
      of({ items: [makeTemplate(), otherOrg], total: 2, limit: 50, offset: 0 }),
    ),
    clonePreview: jest.fn(() => of(makePreview())),
    clone: jest.fn(() => of({ event: makeEvent({ id: 'new-1', state: 'idea' }), report: [] })),
    ...over,
  };
}

async function setup(
  archive = fakeArchive(),
  inputs: Record<string, unknown> = {},
  quotes: unknown = of({ groups: [], suggestedBudgetCents: null }),
) {
  const created = jest.fn();
  const closed = jest.fn();
  const switchToBlank = jest.fn();
  const view = await render(CloneDialogComponent, {
    inputs,
    providers: [
      { provide: ArchiveApi, useValue: archive },
      { provide: EventsApi, useValue: fakeApi() },
      { provide: FormatsApi, useValue: { list: jest.fn(() => of({ items: [{ slug: 'movienight', title: 'Movienight' }], total: 1 })) } },
      { provide: AttachmentsApi, useValue: { quotes: jest.fn(() => quotes) } },
      { provide: AuthService, useValue: fakeAuth() },
    ],
    on: { created, closed, switchToBlank },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return {
    view,
    archive,
    created,
    closed,
    switchToBlank,
    toasts: () => TestBed.inject(ToastService).toasts().map((t) => t.message),
  };
}

async function pickFirst() {
  await userEvent.click(await screen.findByRole('button', { name: 'STUPA Movienight: Whiplash (OmU)' }));
}

async function fillDate() {
  await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2026');
  await userEvent.tab();
  await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:30');
  await userEvent.tab();
}

describe('CloneDialogComponent', () => {
  it('lists the templates grouped by format with the state of their howto', async () => {
    await setup();
    expect(await screen.findByRole('heading', { level: 4, name: 'Movienight' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'Ohne Format' })).toBeInTheDocument();
    expect(screen.getByText('Anleitung geprüft am 12.02.2026')).toBeInTheDocument();
    expect(screen.getByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('says so when no template matches', async () => {
    await setup(fakeArchive({ templates: jest.fn(() => of({ items: [], total: 0, limit: 50, offset: 0 })) }));
    expect(await screen.findByText(/Keine passende Vorlage gefunden/)).toBeInTheDocument();
  });

  it('says so when the list does not load', async () => {
    await setup(fakeArchive({ templates: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Vorlagen konnten nicht geladen werden.');
  });

  it('searches after a short delay with the typed term', async () => {
    const { archive } = await setup();
    await screen.findByRole('button', { name: 'STUPA Movienight: Whiplash (OmU)' });
    await userEvent.type(screen.getByRole('searchbox', { name: 'Vorlagen suchen' }), 'campus');
    await waitFor(() => expect(archive.templates).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'campus' })));
  });

  it('shows the preview, "Letztes Mal" and the quotes of an own template when it is chosen', async () => {
    const quotes = of({
      groups: [
        {
          grp: 'Technik',
          cheapestId: 'q1',
          selectedId: 'q1',
          quotes: [
            { id: 'q1', grp: 'Technik', vendor: 'Beamer GmbH', amountCents: 12000, currency: 'EUR', validUntil: null, selected: true, note: null, attachmentId: null, expired: false, retiredAt: null },
          ],
        },
      ],
      selectedTotalCents: 12000,
      selectedTotalCurrency: 'EUR',
      suggestedBudgetCents: 12000,
    });
    const { archive } = await setup(fakeArchive(), {}, quotes);
    await pickFirst();
    expect(await screen.findByText('Poster: Datum im Bild, bitte neu gestalten')).toBeInTheDocument();
    expect(archive.clonePreview).toHaveBeenCalledWith('tpl-1', 'org-fsi');
    expect(screen.getByText('87')).toBeInTheDocument();
    expect(screen.getByText(/245,00/)).toBeInTheDocument();
    expect(await screen.findByText('Angebote der letzten Auflage')).toBeInTheDocument();
    expect(screen.getByText('Beamer GmbH')).toBeInTheDocument();
    expect(screen.queryByText('Angebote und Businesspläne bleiben bei der ursprünglichen Organisation.')).not.toBeInTheDocument();
  });

  it('notes that offers stay with the original organization for a foreign template and asks for no quotes', async () => {
    const archive = fakeArchive({
      clonePreview: jest.fn(() => of(makePreview({ lastTime: makeLastTime({ costsCents: null, revenueCents: null, restricted: true, source: { ...makeLastTime().source, own: false } }) }))),
    });
    await setup(archive);
    await userEvent.click(await screen.findByRole('button', { name: 'Campusfest 2025' }));
    expect(
      (await screen.findAllByText('Angebote und Businesspläne bleiben bei der ursprünglichen Organisation.')).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText('Angebote der letzten Auflage')).not.toBeInTheDocument();
  });

  it('opens with the template of the link already chosen', async () => {
    const { archive } = await setup(fakeArchive(), { templateId: 'tpl-1' });
    await waitFor(() => expect(archive.clonePreview).toHaveBeenCalledWith('tpl-1', 'org-fsi'));
    expect(await screen.findByText('Was wird übernommen')).toBeInTheDocument();
  });

  it('starts filtered by the format of the link', async () => {
    const { archive } = await setup(fakeArchive(), { formatSlug: 'movienight' });
    await waitFor(() => expect(archive.templates).toHaveBeenLastCalledWith(expect.objectContaining({ format: 'movienight' })));
  });

  it('refuses without a new start and posts nothing', async () => {
    const { archive } = await setup();
    await pickFirst();
    await userEvent.click(await screen.findByRole('button', { name: 'Neu anlegen' }));
    expect(screen.getByText('Neues Datum fehlt.')).toBeInTheDocument();
    expect(archive.clone).not.toHaveBeenCalled();
  });

  it('clones with UTC instants, the title and reports the new dossier', async () => {
    const { archive, created, toasts } = await setup();
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await fillDate();
    await userEvent.type(screen.getByLabelText('Titel'), ' Movienight Spezial ');
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(archive.clone).toHaveBeenCalledWith('tpl-1', {
      startsAt: '2026-11-05T18:30:00Z',
      title: 'Movienight Spezial',
    });
    expect(created).toHaveBeenCalledWith('new-1');
    expect(toasts()).toContain('Neues Dossier aus der Vorlage angelegt.');
  });

  it('asks for no time when the template is all-day and sends noon of the chosen day', async () => {
    const archive = fakeArchive({
      templates: jest.fn(() =>
        of({ items: [makeTemplate({ allDay: true })], total: 1, limit: 50, offset: 0 }),
      ),
    });
    await setup(archive);
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    expect(screen.queryByLabelText(/Beginn, Uhrzeit/)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(archive.clone).toHaveBeenCalledWith('tpl-1', { startsAt: '2026-11-05T11:00:00Z' });
  });

  it('says "Vorlage nicht mehr verfügbar." when the template is gone and reloads the list', async () => {
    const archive = fakeArchive({
      clone: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 409, error: { status: 409, code: 'not_a_template' } }))),
    });
    const { toasts } = await setup(archive);
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    await waitFor(() => expect(toasts()).toContain('Vorlage nicht mehr verfügbar.'));
    expect(archive.templates.mock.calls.length).toBeGreaterThan(1);
  });

  it('says which organization is missing when the server asks for it', async () => {
    const archive = fakeArchive({
      clone: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 422, error: { status: 422, code: 'organization_required' } }))),
    });
    const { toasts } = await setup(archive);
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    await waitFor(() => expect(toasts()).toContain('Bitte wähle die Organisation.'));
  });

  it('lets the person go back to the blank form', async () => {
    const { switchToBlank } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: 'Neu' }));
    expect(switchToBlank).toHaveBeenCalled();
  });

  it('keeps the button off until a template is chosen', async () => {
    await setup();
    await screen.findByRole('button', { name: 'STUPA Movienight: Whiplash (OmU)' });
    expect(screen.getByRole('button', { name: 'Neu anlegen' })).toBeDisabled();
  });

  it('has no axe violations with a chosen template', async () => {
    const { view } = await setup();
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: 'Neu aus Vorlage' })).toBeInTheDocument();
    expect(await runAxe(view.container)).toHaveNoViolations();
  }, 30_000);

  it('refuses an end before the start and sends the end otherwise', async () => {
    const { archive } = await setup();
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await fillDate();
    await userEvent.type(screen.getByLabelText(/Ende, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Ende, Uhrzeit/), '18:00');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(archive.clone).not.toHaveBeenCalled();
    const time = screen.getByLabelText(/Ende, Uhrzeit/);
    await userEvent.clear(time);
    await userEvent.type(time, '21:00');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(archive.clone).toHaveBeenCalledWith('tpl-1', {
      startsAt: '2026-11-05T18:30:00Z',
      endsAt: '2026-11-05T20:00:00Z',
    });
  });

  it('asks for the organization when the person may create in several', async () => {
    const events = fakeApi({
      organizations: jest.fn(() => of([
        { id: 'org-fsi', slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
        { id: 'org-mk', slug: 'makers', name: 'MAKERS', short: 'MKR' },
      ])),
    });
    const archive = fakeArchive();
    await render(CloneDialogComponent, {
      providers: [
        { provide: ArchiveApi, useValue: archive },
        { provide: EventsApi, useValue: events },
        { provide: FormatsApi, useValue: { list: jest.fn(() => of({ items: [], total: 0, limit: 100, offset: 0 })) } },
        { provide: AttachmentsApi, useValue: { quotes: jest.fn(() => of({ groups: [] })) } },
        { provide: AuthService, useValue: fakeAuth({ organizations: () => [{ slug: 'fsi', role: 'organizer' }, { slug: 'makers', role: 'organizer' }] }) },
      ],
    });
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await userEvent.click(screen.getByRole('combobox', { name: /Organisation/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'MAKERS' }));
    await waitFor(() => expect(archive.clonePreview).toHaveBeenLastCalledWith('tpl-1', 'org-mk'));
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    expect(archive.clone).toHaveBeenCalledWith('tpl-1', { startsAt: '2026-11-05T18:30:00Z', organizationId: 'org-mk' });
  });

  it('filters by format, category and year', async () => {
    const { archive } = await setup();
    await screen.findByRole('button', { name: 'STUPA Movienight: Whiplash (OmU)' });
    await userEvent.click(screen.getByRole('button', { name: /^Format/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Movienight' }));
    await waitFor(() => expect(archive.templates).toHaveBeenLastCalledWith(expect.objectContaining({ format: 'movienight' })));
    await userEvent.click(screen.getByRole('button', { name: /^Kategorie/ }));
    await userEvent.click(await screen.findByRole('option', { name: 'Kino' }));
    await waitFor(() => expect(archive.templates).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'kino' })));
    await userEvent.click(screen.getByRole('button', { name: /^Jahr/ }));
    await userEvent.click(await screen.findByRole('option', { name: String(new Date().getFullYear()) }));
    await waitFor(() => expect(archive.templates).toHaveBeenLastCalledWith(expect.objectContaining({ year: String(new Date().getFullYear()) })));
  });

  describe('on a phone', () => {
    const original = window.matchMedia;
    beforeEach(() => {
      window.matchMedia = ((query: string) => ({
        matches: true, media: query, addEventListener: () => undefined, removeEventListener: () => undefined,
      })) as unknown as typeof window.matchMedia;
    });
    afterEach(() => (window.matchMedia = original));

    it('shows the list first, then preview and form as the second step, and goes back', async () => {
      await setup();
      await pickFirst();
      expect(await screen.findByText('Was wird übernommen')).toBeInTheDocument();
      expect(screen.queryByRole('searchbox', { name: 'Vorlagen suchen' })).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', { name: 'Zurück zur Liste' }));
      expect(await screen.findByRole('searchbox', { name: 'Vorlagen suchen' })).toBeInTheDocument();
      expect(screen.queryByText('Was wird übernommen')).not.toBeInTheDocument();
    });

    it('opens on the preview when the link names a template', async () => {
      await setup(fakeArchive(), { templateId: 'tpl-1' });
      expect(await screen.findByText('Was wird übernommen')).toBeInTheDocument();
    });
  });

  it('shows the message of any other refusal of the clone', async () => {
    const archive = fakeArchive({
      clone: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    });
    const { toasts } = await setup(archive);
    await pickFirst();
    await screen.findByText('Was wird übernommen');
    await fillDate();
    await userEvent.click(screen.getByRole('button', { name: 'Neu anlegen' }));
    await waitFor(() => expect(toasts()).toContain('Dafür fehlt dir die Berechtigung.'));
  });
});
