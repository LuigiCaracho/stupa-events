import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { AttachmentsApi } from '../api/attachments-api.service';
import { QuotesTabComponent } from './quotes-tab.component';

const quotes = {
  groups: [
    {
      grp: 'T',
      cheapestId: 'q1',
      selectedId: null,
      quotes: [
        {
          id: 'q1',
          grp: 'T',
          vendor: 'V',
          amountCents: 100,
          currency: 'EUR',
          validUntil: null,
          note: null,
          attachmentId: null,
          selected: false,
          expired: false,
          retiredAt: null,
        },
      ],
    },
  ],
  selectedTotalCents: 0,
  selectedTotalCurrency: 'EUR',
  suggestedBudgetCents: null,
};

function fakeApi(over: Record<string, unknown> = {}) {
  return {
    quotes: jest.fn(() => of(quotes)),
    addQuote: jest.fn(() => of({})),
    selectQuote: jest.fn(() => of({})),
    removeQuote: jest.fn(() => of(undefined)),
    ...over,
  };
}

async function setup(api = fakeApi(), canEdit = true) {
  const changed = jest.fn();
  const view = await render(QuotesTabComponent, {
    inputs: { event: makeEvent(), canEdit },
    on: { changed },
    providers: [{ provide: AttachmentsApi, useValue: api }],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, api, changed };
}

describe('QuotesTabComponent', () => {
  it('creates, chooses and hides quotes and tells the page', async () => {
    const { api, changed } = await setup();
    await userEvent.click(screen.getByRole('radio', { name: 'Angebot von V wählen' }));
    expect(api.selectQuote).toHaveBeenCalledWith('q1');
    expect(changed).toHaveBeenCalled();
    await userEvent.click(screen.getAllByRole('button', { name: 'Ausblenden' }).at(-1) as HTMLElement);
    expect(api.removeQuote).toHaveBeenCalledWith('q1');
    await userEvent.click(screen.getByRole('button', { name: 'Angebot hinzufügen' }));
    const boxes = screen.getAllByRole('textbox');
    await userEvent.type(boxes[0], 'G');
    await userEvent.type(boxes[1], 'W');
    await userEvent.type(boxes[2], '5');
    await userEvent.click(screen.getByRole('button', { name: 'Angebot speichern' }));
    expect(api.addQuote).toHaveBeenCalledWith('ev-1', { grp: 'G', vendor: 'W', amountCents: 500 });
  });

  it('says so when the person may not see quotes', async () => {
    await setup(fakeApi({ quotes: jest.fn(() => throwError(() => new Error('x'))) }));
    expect(screen.getByRole('heading', { name: 'Vergleichsangebote' })).toBeInTheDocument();
    expect(screen.getByText('Vergleichsangebote sind für dich nicht sichtbar.')).toBeInTheDocument();
  });

  it('reports a refused write', async () => {
    const refused = new HttpErrorResponse({ status: 403, error: { status: 403, code: 'forbidden' } });
    const { changed } = await setup(
      fakeApi({ selectQuote: jest.fn(() => throwError(() => refused)) }),
    );
    await userEvent.click(screen.getByRole('radio', { name: 'Angebot von V wählen' }));
    expect(changed).not.toHaveBeenCalled();
    expect(TestBed.inject(ToastService).toasts().map((t) => t.message)).toEqual([
      'Dafür fehlt dir die Berechtigung.',
    ]);
  });
});
