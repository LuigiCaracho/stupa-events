import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeEvent } from '../../../../testing/event-fixtures';
import { FollowupApi } from '../api/followup-api.service';
import { HowtoCheckComponent } from './howto-check.component';

async function setup(api: Record<string, unknown> = {}, inputs: Record<string, unknown> = {}) {
  const changed = jest.fn();
  const fake = {
    verifyHowto: jest.fn(() => of(makeEvent({ howtoVerifiedAt: '2026-10-20T10:00:00Z', howtoVerifiedBy: 'Mara' }))),
    unverifyHowto: jest.fn(() => of(makeEvent())),
    ...api,
  };
  const view = await render(HowtoCheckComponent, {
    inputs: { event: makeEvent({ state: 'followup' }), canEdit: true, ...inputs },
    providers: [{ provide: FollowupApi, useValue: fake }],
    on: { changed },
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, fake, changed };
}

describe('HowtoCheckComponent', () => {
  it('verifies the howto when the box is ticked and reports the dossier', async () => {
    const { fake, changed } = await setup();
    await userEvent.click(screen.getByRole('checkbox', { name: 'Anleitung geprüft' }));
    expect(fake.verifyHowto).toHaveBeenCalledWith('ev-1');
    expect(changed).toHaveBeenCalledWith(expect.objectContaining({ howtoVerifiedBy: 'Mara' }));
  });

  it('shows who checked and when, and removes the mark when unticked', async () => {
    const { fake } = await setup(undefined, {
      event: makeEvent({ state: 'followup', howtoVerifiedAt: '2026-10-20T10:00:00Z', howtoVerifiedBy: 'Mara' }),
    });
    expect(screen.getByText(/Zuletzt geprüft von Mara am/)).toBeInTheDocument();
    const box = screen.getByRole('checkbox', { name: 'Anleitung geprüft' });
    expect(box).toBeChecked();
    await userEvent.click(box);
    expect(fake.unverifyHowto).toHaveBeenCalledWith('ev-1');
  });

  it('cannot take the mark back once the dossier is archived', async () => {
    await setup(undefined, {
      event: makeEvent({ state: 'archived', howtoVerifiedAt: '2026-10-20T10:00:00Z' }),
    });
    expect(screen.getByRole('checkbox', { name: 'Anleitung geprüft' })).toBeDisabled();
  });

  it('can still verify afterwards in the archive', async () => {
    const { fake } = await setup(undefined, { event: makeEvent({ state: 'archived' }) });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Anleitung geprüft' }));
    expect(fake.verifyHowto).toHaveBeenCalled();
  });

  it('is disabled without the right', async () => {
    await setup(undefined, { canEdit: false });
    expect(screen.getByRole('checkbox', { name: 'Anleitung geprüft' })).toBeDisabled();
  });

  it('reports the failure and hands back the unchanged dossier', async () => {
    const { changed } = await setup({
      verifyHowto: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } }))),
    });
    await userEvent.click(screen.getByRole('checkbox', { name: 'Anleitung geprüft' }));
    expect(changed).toHaveBeenCalledWith(expect.objectContaining({ id: 'ev-1' }));
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
