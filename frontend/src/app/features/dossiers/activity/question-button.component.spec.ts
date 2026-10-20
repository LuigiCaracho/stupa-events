import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { CommentsApi } from '../api/comments-api.service';
import { QuestionButtonComponent } from './question-button.component';

async function setup(add = jest.fn(() => of({})), inputs: Record<string, unknown> = {}) {
  const asked = jest.fn();
  const view = await render(QuestionButtonComponent, {
    inputs: { eventId: 'e1', anchor: { field: 'hero' }, what: 'Poster', ...inputs },
    on: { asked },
    providers: [{ provide: CommentsApi, useValue: { add } }],
  });
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return {
    ...view,
    add,
    asked,
    success: jest.spyOn(toast, 'success'),
    error: jest.spyOn(toast, 'error'),
  };
}

describe('QuestionButtonComponent', () => {
  it('posts the question with its anchor and tells the page', async () => {
    const { add, asked, success, container } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage zu Poster' }));
    expect(await runAxe(container)).toHaveNoViolations();
    await userEvent.type(screen.getByLabelText('Deine Rückfrage'), 'Ist das Bild frei?');
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage senden' }));
    expect(add).toHaveBeenCalledWith('e1', {
      bodyMd: 'Ist das Bild frei?',
      anchor: { field: 'hero' },
    });
    expect(success).toHaveBeenCalledWith('Rückfrage gesendet.');
    expect(asked).toHaveBeenCalled();
    expect(screen.queryByLabelText('Deine Rückfrage')).not.toBeInTheDocument();
  });

  it('sends a general question without an anchor under the short label', async () => {
    const { add } = await setup(
      jest.fn(() => of({})),
      { anchor: null, what: '' },
    );
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage' }));
    await userEvent.type(screen.getByLabelText('Deine Rückfrage'), 'Hallo');
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage senden' }));
    expect(add).toHaveBeenCalledWith('e1', { bodyMd: 'Hallo' });
  });

  it('ignores an empty question and can be closed', async () => {
    const { add } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage zu Poster' }));
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage senden' }));
    expect(add).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(screen.queryByLabelText('Deine Rückfrage')).not.toBeInTheDocument();
  });

  it('keeps the box open and shows the refusal', async () => {
    const { error } = await setup(
      jest.fn(() =>
        throwError(
          () =>
            new HttpErrorResponse({ status: 422, error: { status: 422, code: 'anchor_invalid' } }),
        ),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage zu Poster' }));
    await userEvent.type(screen.getByLabelText('Deine Rückfrage'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Rückfrage senden' }));
    expect(error).toHaveBeenCalledWith('Die Rückfrage passt nicht zu diesem Dossier.');
    expect(screen.getByLabelText('Deine Rückfrage')).toBeInTheDocument();
  });
});
