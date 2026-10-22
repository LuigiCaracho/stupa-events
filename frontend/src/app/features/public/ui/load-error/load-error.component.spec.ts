/** Spec for the load error note. */
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { LoadErrorComponent } from './load-error.component';

describe('LoadErrorComponent', () => {
  it('announces the failure and offers a reload that emits retry', async () => {
    const retry = jest.fn();
    await render(LoadErrorComponent, { inputs: { kind: 'failed' }, on: { retry } });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Termine konnten nicht geladen werden.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Neu laden' }));
    expect(retry).toHaveBeenCalled();
  });

  it('tells the visitor to wait on 429', async () => {
    await render(LoadErrorComponent, { inputs: { kind: 'rateLimited' } });
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Zu viele Anfragen. Bitte warte einen Moment.',
    );
  });

  it('has a sentence for a too long search and no reload for it', async () => {
    await render(LoadErrorComponent, { inputs: { kind: 'queryTooLong' } });
    expect(screen.getByRole('alert')).toHaveTextContent('Suchbegriff zu lang.');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
