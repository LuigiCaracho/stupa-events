import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi } from '../../../../testing/event-fixtures';
import type { RevisionOut } from '../api/action.models';
import { EventsApi } from '../api/events-api.service';
import { DossierHistoryComponent } from './dossier-history.component';

const rev = (n: number, over: Partial<RevisionOut> = {}): RevisionOut => ({
  rev: n,
  at: '2026-10-18T12:02:00Z',
  actor: { sub: 'u', displayName: 'Anna' },
  actorType: 'human',
  changeNote: null,
  changedFields: ['summary'],
  ...over,
});

async function setup(
  items: RevisionOut[],
  canRevert = true,
  api = fakeApi({
    revisions: jest.fn(() => of({ items, total: items.length, limit: 50, offset: 0 })),
  }),
) {
  const revert = jest.fn();
  const view = await render(DossierHistoryComponent, {
    inputs: { eventId: 'ev-1', rev: 5, canRevert },
    providers: [{ provide: EventsApi, useValue: api }],
    on: { revert },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, api, revert };
}

describe('DossierHistoryComponent', () => {
  it('lists the revisions with person, state change mark, note and the changed fields', async () => {
    const { api } = await setup([
      rev(5, { changeNote: 'Tippfehler', changedFields: ['summary', 'starts_at'] }),
      rev(4, { changedFields: ['state'] }),
      rev(3, { actorType: 'system', changedFields: ['title'] }),
    ]);
    expect(api.revisions).toHaveBeenCalledWith('ev-1');
    expect(screen.getByText('Fassung 5')).toBeInTheDocument();
    expect(screen.getByText('Tippfehler')).toBeInTheDocument();
    expect(screen.getAllByText('Zustandswechsel')).toHaveLength(1);
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Kurztext')).toBeInTheDocument();
    expect(screen.getByText('Beginn')).toBeInTheDocument();
  });

  it('offers the reset for older revisions only', async () => {
    const { revert } = await setup([rev(5), rev(4), rev(3)]);
    const buttons = screen.getAllByRole('button', { name: 'Auf diesen Stand zurücksetzen' });
    expect(buttons).toHaveLength(2);
    await userEvent.click(buttons[0]);
    expect(revert).toHaveBeenCalledWith(4);
  });

  it('offers no reset without the right', async () => {
    await setup([rev(5), rev(4)], false);
    expect(
      screen.queryByRole('button', { name: 'Auf diesen Stand zurücksetzen' }),
    ).not.toBeInTheDocument();
  });

  it('shows an unknown actor as a question mark and an error note when the load fails', async () => {
    await setup([rev(4, { actor: { sub: 'x', displayName: null } })]);
    expect(screen.getByText('?')).toBeInTheDocument();
  });

  it('says so when the history cannot be loaded and has no axe violations', async () => {
    const api = fakeApi({
      revisions: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))),
    });
    const { view } = await setup([], true, api);
    expect(screen.getByRole('alert')).toHaveTextContent('Der Verlauf konnte nicht geladen werden.');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
