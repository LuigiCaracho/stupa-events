import { DeferBlockBehavior } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { MediaApiService } from '@shared/markdown/media-api.service';
import { of } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import { DocumentsApi } from '../api/documents-api.service';
import { FollowupApi } from '../api/followup-api.service';
import { FollowupTabComponent } from './followup-tab.component';

const reasons = [
  { code: 'retrospective_missing', field: null, severity: 'blocker' as const, messageKey: 'guards.retrospective_missing', fixAction: 'fill_retrospective' as const },
  { code: 'outcome_missing', field: null, severity: 'blocker' as const, messageKey: 'guards.outcome_missing', fixAction: 'fill_outcome' as const },
  { code: 'howto_unverified', field: null, severity: 'blocker' as const, messageKey: 'guards.howto_unverified', fixAction: 'verify_howto' as const },
  { code: 'checklist_open', field: 'followup', severity: 'blocker' as const, messageKey: 'guards.checklist_open', fixAction: 'open_checklist' as const },
];

async function setup(inputs: Record<string, unknown> = {}) {
  const outputs = { changed: jest.fn(), fix: jest.fn(), finish: jest.fn(), openChecklist: jest.fn() };
  const view = await render(FollowupTabComponent, {
    inputs: {
      event: makeEvent({ state: 'followup', allowedTransitions: ['T09'] }),
      canEdit: true,
      guards: makeGuards({ transition: 'T09', allowed: false, reasons }),
      ...inputs,
    },
    on: outputs,
    deferBlockBehavior: DeferBlockBehavior.Playthrough,
    providers: [
      { provide: DocumentsApi, useValue: { list: jest.fn(() => of([])), create: jest.fn() } },
      { provide: FollowupApi, useValue: { putOutcome: jest.fn(), verifyHowto: jest.fn(), unverifyHowto: jest.fn() } },
      { provide: MediaApiService, useValue: { uploadImage: jest.fn() } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, ...outputs };
}

describe('FollowupTabComponent', () => {
  afterEach(() => localStorage.clear());

  it('lists what T09 still misses, in the order of the contract, with the sentences of the guards', async () => {
    await setup();
    const rows = screen.getAllByText(/fehlt|offen|geprüft/i);
    expect(rows.length).toBeGreaterThan(0);
    expect(screen.getByText('Die Nachbereitung fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Das Ergebnis fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Die Anleitung ist noch nicht geprüft.')).toBeInTheDocument();
    expect(screen.getByText('Pflichtpunkte der Checkliste sind offen.')).toBeInTheDocument();
  });

  it('forwards the fix buttons to the page', async () => {
    const { fix } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Rückblick schreiben' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ergebnis eintragen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Anleitung prüfen' }));
    expect(fix.mock.calls.map((c) => c[0].fixAction)).toEqual(['fill_retrospective', 'fill_outcome', 'verify_howto']);
  });

  it('asks the page to run T09 with the button', async () => {
    const { finish } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Nachbereitung abschließen' }));
    expect(finish).toHaveBeenCalled();
  });

  it('offers no finish button when the server does not allow T09', async () => {
    await setup({ event: makeEvent({ state: 'followup', allowedTransitions: [] }) });
    expect(screen.queryByRole('button', { name: 'Nachbereitung abschließen' })).not.toBeInTheDocument();
  });

  it('has the three sections and the way to the checklist', async () => {
    const { openChecklist } = await setup();
    expect(screen.getByRole('heading', { name: 'Rückblick' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Ergebnis' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Anleitung prüfen' })).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Checkliste öffnen' }).at(-1)!);
    expect(openChecklist).toHaveBeenCalled();
  });

  it('shows no guard list in live, only the hint that the follow-up begins soon', async () => {
    await setup({ event: makeEvent({ state: 'live' }), guards: null });
    expect(screen.getByText(/Die Nachbereitung beginnt kurz nach dem Ende/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Nachbereitung abschließen' })).not.toBeInTheDocument();
  });

  it('is read only in the archive and says so', async () => {
    await setup({ event: makeEvent({ state: 'archived', allowedTransitions: [] }), guards: null });
    expect(screen.getByText(/Die Nachbereitung ist abgeschlossen/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ergebnis speichern' })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Anleitung geprüft' })).toBeEnabled();
  });

  it('keeps the verify tick off for a person without the action', async () => {
    await setup({ event: makeEvent({ state: 'followup', allowedActions: [], allowedTransitions: ['T09'] }) });
    expect(screen.getByRole('checkbox', { name: 'Anleitung geprüft' })).toBeDisabled();
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  }, 30_000);
});
