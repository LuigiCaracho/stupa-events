import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, makeEvent } from '../../../../testing/event-fixtures';
import { EventsApi } from '../api/events-api.service';
import { AssignOrgDialogComponent } from './assign-org-dialog.component';

async function setup(api = fakeApi()) {
  const done = jest.fn();
  const stale = jest.fn();
  const closed = jest.fn();
  await render(AssignOrgDialogComponent, {
    inputs: { event: makeEvent({ organization: null, state: 'idea', rev: 2 }) },
    providers: [{ provide: EventsApi, useValue: api }],
    on: { done, stale, closed },
  });
  return {
    api,
    done,
    stale,
    closed,
    toasts: () =>
      TestBed.inject(ToastService)
        .toasts()
        .map((t) => t.message),
  };
}

describe('AssignOrgDialogComponent', () => {
  it('needs a choice and then assigns the organization', async () => {
    const { api, done } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Zuweisen' }));
    expect(screen.getByText('Organisation fehlt.')).toBeInTheDocument();
    expect(api.action).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('combobox', { name: /Organisation/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Fachschaft Informatik' }));
    await userEvent.click(screen.getByRole('button', { name: 'Zuweisen' }));
    expect(api.action).toHaveBeenCalledWith(
      'ev-1',
      'assign-organization',
      { organizationId: 'org-fsi' },
      2,
    );
    expect(done).toHaveBeenCalled();
  });

  it('reports a dossier that already has an organization', async () => {
    const set = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'organization_already_set' },
    });
    const { stale, toasts, done } = await setup(
      fakeApi({ action: jest.fn(() => throwError(() => set)) }),
    );
    await userEvent.click(screen.getByRole('combobox', { name: /Organisation/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Fachschaft Informatik' }));
    await userEvent.click(screen.getByRole('button', { name: 'Zuweisen' }));
    expect(toasts()).toEqual(['Dem Dossier ist schon eine Organisation zugewiesen.']);
    expect(stale).toHaveBeenCalled();
    expect(done).not.toHaveBeenCalled();
  });

  it('shows another failure without a reload and has no axe violations', async () => {
    const down = new HttpErrorResponse({ status: 500 });
    const { stale, toasts, closed } = await setup(
      fakeApi({ action: jest.fn(() => throwError(() => down)) }),
    );
    await userEvent.click(screen.getByRole('combobox', { name: /Organisation/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Fachschaft Informatik' }));
    await userEvent.click(screen.getByRole('button', { name: 'Zuweisen' }));
    expect(toasts()[0]).toContain('Das hat nicht geklappt');
    expect(stale).not.toHaveBeenCalled();
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });
});
