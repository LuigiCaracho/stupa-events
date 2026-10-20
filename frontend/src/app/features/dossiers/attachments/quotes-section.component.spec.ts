import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import type { QuotesOut } from '../model/attachment.models';
import { QuotesSectionComponent } from './quotes-section.component';

const quotes: QuotesOut = {
  groups: [
    {
      grp: 'Technik',
      cheapestId: 'q1',
      selectedId: 'q1',
      quotes: [
        {
          id: 'q1',
          grp: 'Technik',
          vendor: 'Licht',
          amountCents: 50000,
          currency: 'EUR',
          validUntil: null,
          note: null,
          attachmentId: null,
          selected: true,
          expired: false,
          retiredAt: null,
        },
      ],
    },
  ],
  selectedTotalCents: 50000,
  selectedTotalCurrency: 'EUR',
  suggestedBudgetCents: 60000,
};

async function setup(inputs: Record<string, unknown> = {}) {
  const on = { add: jest.fn(), select: jest.fn(), remove: jest.fn(), budget: jest.fn() };
  const view = await render(QuotesSectionComponent, {
    inputs: { quotes, canEdit: true, ...inputs },
    on,
  });
  return { ...view, on };
}

describe('QuotesSectionComponent', () => {
  it('shows the sum of the choice and hands the budget suggestion to the page', async () => {
    const { on } = await setup();
    expect(screen.getByText('500,00 €', { selector: 'strong' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Als Budget übernehmen' }));
    expect(on.budget).toHaveBeenCalledWith(60000);
  });

  it('shows no sum when nothing is chosen and no controls for a reader', async () => {
    await setup({
      canEdit: false,
      quotes: { ...quotes, groups: [{ ...quotes.groups[0], selectedId: null }] },
    });
    expect(screen.queryByText('Summe der Auswahl:')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Angebot hinzufügen' })).not.toBeInTheDocument();
  });

  it('validates and sends a new quote in cents', async () => {
    const { on } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Angebot hinzufügen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Angebot speichern' }));
    expect(on.add).not.toHaveBeenCalled();
    expect(screen.getByText('Bitte eine Gruppe angeben.')).toBeInTheDocument();
    const boxes = screen.getAllByRole('textbox');
    await userEvent.type(boxes[0], 'Catering');
    await userEvent.type(boxes[1], 'Küche AG');
    await userEvent.type(boxes[2], '12,50');
    await userEvent.click(screen.getByRole('button', { name: 'Angebot speichern' }));
    expect(on.add).toHaveBeenCalledWith({ grp: 'Catering', vendor: 'Küche AG', amountCents: 1250 });
    expect(screen.queryByRole('button', { name: 'Angebot speichern' })).not.toBeInTheDocument();
  });

  it('can close the form again', async () => {
    await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Angebot hinzufügen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(screen.getByRole('button', { name: 'Angebot hinzufügen' })).toBeInTheDocument();
  });

  it('passes select and remove through', async () => {
    const { on } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Ausblenden' }));
    expect(on.remove).toHaveBeenCalledWith('q1');
  });
});
