import { HttpErrorResponse } from '@angular/common/http';
import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { SessionsApi } from '../../admin/api/sessions-api.service';
import { SessionSectionComponent } from './session-section.component';

async function setup(revokeOwn = jest.fn(() => of({ revoked: 3 }))) {
  const view = await render(SessionSectionComponent, {
    providers: [{ provide: SessionsApi, useValue: { revokeOwn } }],
  });
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return {
    ...view,
    revokeOwn,
    success: jest.spyOn(toast, 'success'),
    error: jest.spyOn(toast, 'error'),
  };
}

describe('SessionSectionComponent', () => {
  it('asks before it revokes and reports the count', async () => {
    const { revokeOwn, success } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Andere Sitzungen widerrufen' }));
    const dialog = await screen.findByRole('dialog');
    expect(revokeOwn).not.toHaveBeenCalled();
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Andere Sitzungen widerrufen' }),
    );
    expect(revokeOwn).toHaveBeenCalledTimes(1);
    expect(success).toHaveBeenCalledWith('3 Sitzungen beendet.');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('does not call the API when the dialog is cancelled', async () => {
    const { revokeOwn } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Andere Sitzungen widerrufen' }));
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', { name: 'Abbrechen' }),
    );
    expect(revokeOwn).not.toHaveBeenCalled();
  });

  it('keeps the dialog and shows an error when the server refuses', async () => {
    const { error } = await setup(
      jest.fn(() =>
        throwError(
          () => new HttpErrorResponse({ status: 500, error: { status: 500, traceId: 't1' } }),
        ),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Andere Sitzungen widerrufen' }));
    await userEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', {
        name: 'Andere Sitzungen widerrufen',
      }),
    );
    expect(error).toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await setup();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
