import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../testing/a11y';
import type { QuoteGroup, QuoteOut } from '../../../features/dossiers/model/attachment.models';
import { QuoteTableComponent } from './quote-table.component';

const quote = (o: Partial<QuoteOut>): QuoteOut => ({
  id: 'q1',
  grp: 'Technik',
  vendor: 'Licht GmbH',
  amountCents: 123450,
  currency: 'EUR',
  validUntil: '2026-12-01',
  note: null,
  attachmentId: null,
  selected: false,
  expired: false,
  retiredAt: null,
  ...o,
});

const group: QuoteGroup = {
  grp: 'Technik',
  cheapestId: 'q2',
  selectedId: 'q1',
  quotes: [
    quote({ selected: true }),
    quote({ id: 'q2', vendor: 'Ton AG', amountCents: 90000, validUntil: null }),
    quote({ id: 'q3', vendor: 'Alt', expired: true }),
  ],
};

describe('QuoteTableComponent', () => {
  it('marks the cheapest, the chosen and the expired quote with words', async () => {
    const { container } = await render(QuoteTableComponent, { inputs: { group, canEdit: true } });
    expect(screen.getByText('günstigstes')).toBeInTheDocument();
    expect(screen.getByText('abgelaufen')).toBeInTheDocument();
    expect(screen.getByText('unbefristet')).toBeInTheDocument();
    expect(screen.getByText('gewählt', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getAllByText(/1\.234,50/).length).toBeGreaterThan(0);
    expect(screen.getByRole('radio', { name: 'Angebot von Alt wählen' })).toBeDisabled();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it('emits the choice and the removal', async () => {
    const select = jest.fn();
    const remove = jest.fn();
    await render(QuoteTableComponent, {
      inputs: { group, canEdit: true },
      on: { select, remove },
    });
    await userEvent.click(screen.getByRole('radio', { name: 'Angebot von Ton AG wählen' }));
    expect(select).toHaveBeenCalledWith('q2');
    await userEvent.click(screen.getAllByRole('button', { name: 'Ausblenden' })[0]);
    expect(remove).toHaveBeenCalledWith('q1');
  });

  it('has no edit controls for a reader', async () => {
    await render(QuoteTableComponent, { inputs: { group, canEdit: false } });
    expect(screen.queryByRole('button', { name: 'Ausblenden' })).not.toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Angebot von Ton AG wählen' })).toBeDisabled();
  });
});
