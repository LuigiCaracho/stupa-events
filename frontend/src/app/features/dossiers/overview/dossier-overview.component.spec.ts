import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import type { RevisionOut } from '../api/action.models';
import { DossierOverviewComponent } from './dossier-overview.component';

const blocker = {
  code: 'image_required',
  field: null,
  severity: 'blocker' as const,
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster' as const,
};
const change: RevisionOut = {
  rev: 5,
  at: '2026-10-18T12:02:00Z',
  actor: { sub: 'u2', displayName: 'Anna' },
  actorType: 'human',
  fieldClass: 'text',
  changeNote: null,
  changedFields: ['summary', 'cost_text'],
};

describe('DossierOverviewComponent', () => {
  it('lists "Fehlt noch" with the fix button and reports the click', async () => {
    const fix = jest.fn();
    await render(DossierOverviewComponent, {
      inputs: { event: makeEvent(), guards: makeGuards({ allowed: false, reasons: [blocker] }) },
      on: { fix },
    });
    expect(screen.getByRole('heading', { name: 'Fehlt noch' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(fix).toHaveBeenCalledWith(blocker);
  });

  it('shows a skeleton while the guards load and nothing without a next transition', async () => {
    const { container } = await render(DossierOverviewComponent, {
      inputs: { event: makeEvent(), guardsLoading: true },
    });
    expect(container.querySelector('app-skeleton')).not.toBeNull();
    expect(screen.queryByRole('heading', { name: 'Fehlt noch' })).not.toBeInTheDocument();
  });

  it.each([
    ['in_review', 'In der Freigabe gesperrt. Kommentiere, wenn sich etwas ändern soll.'],
    ['approved', 'Freigegeben und gesperrt. Zum Ändern nimm die Freigabe zurück.'],
    ['live_critical', 'Änderung von Zeit, Ort, Titel oder Poster geht über die Redaktion.'],
    ['closed', 'Dieses Dossier ist abgeschlossen.'],
  ] as const)('says why a dossier is locked (%s)', async (lockReason, text) => {
    await render(DossierOverviewComponent, { inputs: { event: makeEvent({ lockReason }) } });
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('names a granted image exception', async () => {
    await render(DossierOverviewComponent, {
      inputs: {
        event: makeEvent({
          imageException: {
            grantedBy: 'e',
            reason: 'Offenes Präsidium',
            at: '2026-10-01T10:00:00Z',
          },
        }),
      },
    });
    expect(screen.getByText('Ausnahme ohne Bild: Offenes Präsidium')).toBeInTheDocument();
  });

  it('shows what changed after publishing and lets reviewers reset or acknowledge', async () => {
    const revert = jest.fn();
    const acknowledge = jest.fn();
    await render(DossierOverviewComponent, {
      inputs: { event: makeEvent({ state: 'live' }), changes: [change] },
      on: { revert, acknowledge },
    });
    expect(
      screen.getByText(/Seit der Veröffentlichung geändert: Kurztext, Kosten \(Anna, /),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Zurücksetzen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Gesehen' }));
    expect(revert).toHaveBeenCalled();
    expect(acknowledge).toHaveBeenCalled();
  });

  it('shows the core data as rows when nothing is editable', async () => {
    const { container } = await render(DossierOverviewComponent, {
      inputs: {
        event: makeEvent({ venue: { id: 'v', slug: 'k', name: 'Kinosaal' }, summary: null }),
        readOnly: true,
      },
    });
    expect(screen.getByText('Kinosaal')).toBeInTheDocument();
    expect(screen.getByText('Kino')).toBeInTheDocument();
    expect(screen.getAllByText('nicht angegeben')).toHaveLength(1);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('falls back to the venue text', async () => {
    await render(DossierOverviewComponent, { inputs: { event: makeEvent(), readOnly: true } });
    expect(screen.getByText('Kinosaal 9-133')).toBeInTheDocument();
  });
});
