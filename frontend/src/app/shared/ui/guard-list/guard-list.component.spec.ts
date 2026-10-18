import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import type { ProblemReason } from '@core/api/models';
import { runAxe } from '../../../../testing/a11y';
import { GuardListComponent } from './guard-list.component';

const warning: ProblemReason = {
  code: 'start_in_past',
  field: 'startsAt',
  severity: 'warning',
  messageKey: 'guards.start_in_past',
  fixAction: 'change_date',
};
const poster: ProblemReason = {
  code: 'image_required',
  field: null,
  severity: 'blocker',
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster',
};
const missing: ProblemReason = {
  code: 'field_missing',
  field: 'venue_text',
  severity: 'blocker',
  messageKey: 'guards.field_missing',
  fixAction: 'fill_field',
};
const waiting: ProblemReason = {
  ...missing,
  code: 'four_eyes',
  field: null,
  messageKey: 'guards.four_eyes',
  fixAction: null,
};

describe('GuardListComponent', () => {
  it('shows the ready message for an empty list', async () => {
    await render(GuardListComponent, { inputs: { reasons: [] } });
    expect(screen.getByRole('heading', { name: 'Fehlt noch' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Alles bereit.');
  });

  it('lists blockers before warnings and names the field', async () => {
    const { container } = await render(GuardListComponent, {
      inputs: { reasons: [warning, missing, poster] },
    });
    const rows = Array.from(container.querySelectorAll('li')).map((li) =>
      li.getAttribute('data-code'),
    );
    expect(rows).toEqual(['field_missing', 'image_required', 'start_in_past']);
    expect(screen.getByText('Es fehlt: Ort.')).toBeInTheDocument();
  });

  it('emits the reason of a fix button and omits the button without fixAction', async () => {
    const fix = jest.fn();
    await render(GuardListComponent, { inputs: { reasons: [poster, waiting] }, on: { fix } });
    expect(screen.getAllByRole('button')).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(fix).toHaveBeenCalledWith(poster);
  });

  it('falls back to the generic text for an unknown message key', async () => {
    await render(GuardListComponent, {
      inputs: { reasons: [{ ...waiting, messageKey: 'guards.other' }] },
    });
    expect(screen.getByText('Voraussetzung nicht erfüllt.')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const { container } = await render(GuardListComponent, {
      inputs: { reasons: [poster, warning] },
    });
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
