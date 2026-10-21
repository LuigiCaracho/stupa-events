/** The M5 additions of the dossier page: the tab Nachbereitung, the fixes of T09, the location and format dialogs and the palette command. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { DeferBlockBehavior, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of } from 'rxjs';
import type { FixAction, ProblemReason } from '@core/api/models';
import { AuthService } from '@core/auth/auth.service';
import { fakeApi, fakeAuth, makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import { makeFormat } from '../../../../testing/m5-fixtures';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { AttachmentsApi } from '../api/attachments-api.service';
import { ChecklistApi } from '../api/checklist-api.service';
import { CommentsApi } from '../api/comments-api.service';
import { DocumentsApi } from '../api/documents-api.service';
import { DossierCommands } from '../api/dossier-commands';
import type { EventDto } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { MailTemplatesApi } from '../api/mail-templates-api.service';
import { DossierDetailComponent } from './dossier-detail.component';

const reason = (code: string, fixAction: FixAction): ProblemReason => ({
  code, field: null, severity: 'blocker', messageKey: `guards.${code}`, fixAction,
});

async function setup(event: EventDto, opts: { can?: string[]; guards?: unknown; routeData?: Record<string, unknown>; counts?: Record<string, number> } = {}) {
  const api = fakeApi({
    get: jest.fn(() => of(event)),
    guards: jest.fn(() => of(opts.guards ?? makeGuards({ transition: 'T09' }))),
  });
  const can = opts.can ?? ['event.edit'];
  const view = await render(DossierDetailComponent, {
    inputs: { id: event.id },
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      provideRouter([]),
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: EventsApi, useValue: api },
      { provide: AuthService, useValue: fakeAuth({ can: (p: string) => can.includes(p) }) },
      { provide: ActivatedRoute, useValue: { snapshot: { data: opts.routeData ?? {}, queryParamMap: new Map() } } },
      { provide: AttachmentsApi, useValue: { counts: jest.fn(() => of({ attachments: 0, howto: 1, openChecklist: 0, mailTemplates: 0, openComments: 0, ...opts.counts })), list: jest.fn(() => of([])), quotes: jest.fn(() => of(null)) } },
      { provide: DocumentsApi, useValue: { list: jest.fn(() => of([])), revisions: jest.fn(() => of([])), create: jest.fn() } },
      { provide: ChecklistApi, useValue: { get: jest.fn(() => of({ items: [], openRequired: { planning: 0, review: 0, live: 0, followup: 0 }, template: null })) } },
      { provide: MailTemplatesApi, useValue: { list: jest.fn(() => of([])), placeholders: jest.fn(() => of([])) } },
      { provide: CommentsApi, useValue: { list: jest.fn(() => of([])) } },
      { provide: ArchiveApi, useValue: { lastTime: jest.fn(() => of(null)), event: jest.fn() } },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  view.fixture.detectChanges();
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const router = TestBed.inject(Router);
  return {
    view, api,
    navigate: jest.spyOn(router, 'navigate').mockResolvedValue(true),
    http: TestBed.inject(HttpTestingController),
  };
}

const followup = (over: Partial<EventDto> = {}): EventDto =>
  makeEvent({ state: 'followup', allowedTransitions: ['T09'], allowedActions: ['verify-howto', 'save-as-format'], editableFields: [], ...over });

describe('DossierDetailComponent (M5)', () => {
  afterEach(() => localStorage.clear());

  it('shows the tab Nachbereitung in followup with the open blockers as its count', async () => {
    await setup(followup(), { counts: { followupOpen: 3 } });
    expect(screen.getByRole('tab', { name: /^Nachbereitung\s*3/ })).toBeInTheDocument();
  });

  it('has no such tab before the end of a live event, and has it after', async () => {
    await setup(makeEvent({ state: 'live', endsAt: '2999-01-01T10:00:00Z', allowedTransitions: [] }));
    expect(screen.queryByRole('tab', { name: /Nachbereitung/ })).not.toBeInTheDocument();
  });

  it('shows the tab for a live event whose end has passed and for an archived dossier', async () => {
    await setup(makeEvent({ state: 'live', endsAt: '2020-01-01T10:00:00Z', allowedTransitions: [] }));
    expect(screen.getByRole('tab', { name: /Nachbereitung/ })).toBeInTheDocument();
  });

  it('opens on the tab Nachbereitung for the route /dossiers/:id/nachbereitung', async () => {
    await setup(followup(), { routeData: { tab: 'followup' }, guards: makeGuards({ transition: 'T09', allowed: false, reasons: [reason('outcome_missing', 'fill_outcome')] }) });
    expect(screen.getByRole('tab', { name: /Nachbereitung/ })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText('Das Ergebnis fehlt.')).toBeInTheDocument();
  });

  it('opens the transition dialog T09 from the finish button', async () => {
    await setup(followup(), { routeData: { tab: 'followup' } });
    await userEvent.click((await screen.findAllByRole('button', { name: 'Nachbereitung abschließen' })).at(-1)!);
    expect(await screen.findByRole('dialog', { name: 'Nachbereitung abschließen' })).toBeInTheDocument();
  });

  it('sends the follow-up fixes to the tab and the checklist fix to the checklist', async () => {
    const guards = makeGuards({
      transition: 'T09', allowed: false,
      reasons: [reason('retrospective_missing', 'fill_retrospective'), reason('checklist_open', 'open_checklist')],
    });
    await setup(followup(), { guards });
    await userEvent.click(await screen.findByRole('button', { name: 'Rückblick schreiben' }));
    expect(screen.getByRole('tab', { name: /Nachbereitung/ })).toHaveAttribute('aria-selected', 'true');
    await userEvent.click(screen.getAllByRole('button', { name: 'Checkliste öffnen' })[0]);
    expect(screen.getByRole('tab', { name: /Checkliste/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('opens the location dialog from the guard fix and confirms the place', async () => {
    const guards = makeGuards({
      transition: 'T04', allowed: false,
      reasons: [reason('location_unconfirmed', 'confirm_location')],
    });
    const { http } = await setup(makeEvent({ state: 'in_review', allowedTransitions: ['T04'], venueText: 'Kinosaal 9-133' }), { guards });
    await userEvent.click(await screen.findByRole('button', { name: 'Ort bestätigen' }));
    expect(screen.getByText('Der Ort ist öffentlich. Keine Privatadresse.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Ort bestätigen' }).at(-1)!);
    const req = http.expectOne('/api/events/ev-1/actions/confirm-location');
    expect(req.request.body).toEqual({ precision: 'building' });
    req.flush(makeEvent({ rev: 4, locationPrecision: 'building' }));
    await TestBed.inject(Router).navigateByUrl('/');
  });

  it('focuses the facts block for the fix "Angaben ergänzen"', async () => {
    const guards = makeGuards({
      transition: 'T02', allowed: false,
      reasons: [reason('facts_invalid', 'fill_facts')],
    });
    await setup(makeEvent({ allowedTransitions: ['T02'] }), { guards });
    await userEvent.click(await screen.findByRole('button', { name: 'Angaben ergänzen' }));
    await new Promise((r) => setTimeout(r));
    expect(screen.getByRole('heading', { name: 'Rahmen' })).toHaveFocus();
  });

  it('shows the facts block of the profile in the overview', async () => {
    await setup(makeEvent({ primaryCategory: { id: 'c', slug: 'p', name: 'Party', kind: 'format', requiredProfile: 'party' } }));
    expect(screen.getByRole('heading', { name: 'Rahmen' })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /Altersgrenze/ })).toBeInTheDocument();
  });

  it('opens "Als Format speichern" from the menu, with the title as the suggestion', async () => {
    await setup(followup({ state: 'archived', allowedTransitions: [] }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Als Format speichern' }));
    expect(await screen.findByRole('dialog', { name: 'Als Format speichern' })).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Movienight')).toBeInTheDocument();
  });

  it('answers the palette command "Als Format speichern" when the dossier allows it', async () => {
    await setup(followup({ state: 'archived', allowedTransitions: [] }));
    TestBed.inject(DossierCommands).send('save-as-format');
    expect(await screen.findByRole('dialog', { name: 'Als Format speichern' })).toBeInTheDocument();
    expect(TestBed.inject(DossierCommands).pending()).toBeNull();
  });

  it('ignores the palette command when the dossier does not allow the action', async () => {
    await setup(followup({ state: 'archived', allowedTransitions: [], allowedActions: [] }));
    TestBed.inject(DossierCommands).send('save-as-format');
    await new Promise((r) => setTimeout(r));
    expect(screen.queryByRole('dialog', { name: 'Als Format speichern' })).not.toBeInTheDocument();
    expect(TestBed.inject(DossierCommands).pending()).toBeNull();
  });

  it('opens the clone dialog of the template from the menu', async () => {
    const { navigate } = await setup(followup({ state: 'archived', allowedTransitions: [], allowedActions: ['clone'] }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Neu aus diesem Event' }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers/neu'], { queryParams: { vorlage: 'ev-1' } });
  });

  it('warns "Anleitung ungeprüft" in the head of an archived dossier with a howto', async () => {
    await setup(followup({ state: 'archived', allowedTransitions: [], allowedActions: [], howtoUnverified: true }));
    expect(await screen.findByText('Anleitung ungeprüft')).toBeInTheDocument();
  });

  it('shows no warning once the howto is checked', async () => {
    await setup(followup({ state: 'archived', allowedTransitions: [], allowedActions: [], howtoVerifiedAt: '2026-10-01T10:00:00Z' }));
    await new Promise((r) => setTimeout(r));
    expect(screen.queryByText('Anleitung ungeprüft')).not.toBeInTheDocument();
  });

  it('shows the format of the dossier as a link in the head', async () => {
    await setup(followup({ format: { slug: makeFormat().slug, title: 'Movienight' } }));
    expect(screen.getByRole('link', { name: 'Movienight' })).toHaveAttribute('href', '/formate/movienight');
  });

  it('takes the dossier that the result form returns', async () => {
    const { http } = await setup(followup(), { routeData: { tab: 'followup' } });
    await userEvent.type(await screen.findByLabelText('Besucher:innen'), '12');
    await userEvent.type(screen.getByLabelText(/Kosten \(Ist\)/), '5');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis speichern' }));
    const req = http.expectOne('/api/events/ev-1/outcome');
    expect(req.request.headers.get('If-Match')).toBe('"3"');
    req.flush(followup({ rev: 4, title: 'Movienight 2' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Movienight 2' })).toBeInTheDocument();
  });

  it('reloads the dossier after the retrospective was created', async () => {
    const { api } = await setup(followup(), { routeData: { tab: 'followup' } });
    const before = api.get.mock.calls.length;
    const docs = TestBed.inject(DocumentsApi) as unknown as { create: jest.Mock };
    docs.create.mockReturnValue(of({ id: 'r1', kind: 'retrospective', title: 'Rückblick', visibility: 'org', carryOver: false, rev: 1, verifiedAt: null, verifiedBy: null, updatedAt: '' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Rückblick speichern' }));
    expect(docs.create).toHaveBeenCalled();
    await new Promise((r) => setTimeout(r));
    expect(api.get.mock.calls.length).toBeGreaterThan(before);
  });

  it('opens the location dialog from the menu "Ort bestätigen"', async () => {
    await setup(makeEvent({ state: 'live', allowedTransitions: [], allowedActions: ['confirm-location'], venueText: 'Kinosaal' }));
    await userEvent.click(screen.getByRole('button', { name: 'Mehr' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Ort bestätigen' }));
    expect(await screen.findByRole('dialog', { name: 'Ort ist öffentlich?' })).toBeInTheDocument();
  });
});
