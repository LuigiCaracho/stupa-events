import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import { of, throwError } from 'rxjs';
import { makeEvent } from '../../../../testing/event-fixtures';
import { makeLastTime } from '../../../../testing/m5-fixtures';
import { ArchiveApi } from '../../archive/api/archive-api.service';
import { AttachmentsApi } from '../api/attachments-api.service';
import { LastTimeBlockComponent } from './last-time-block.component';

const quotes = {
  groups: [
    {
      grp: 'Technik', cheapestId: 'q1', selectedId: 'q1',
      quotes: [{ id: 'q1', grp: 'Technik', vendor: 'Beamer GmbH', amountCents: 12000, currency: 'EUR', validUntil: null, note: null, attachmentId: null, selected: true, expired: false, retiredAt: null }],
    },
  ],
  selectedTotalCents: 12000, selectedTotalCurrency: 'EUR', suggestedBudgetCents: 12000,
};

async function setup(event = makeEvent({ derivedFromId: 'tpl-1' }), lastTime: jest.Mock = jest.fn(() => of(makeLastTime())), quotesCall = jest.fn(() => of(quotes))) {
  const view = await render(LastTimeBlockComponent, {
    inputs: { event },
    providers: [
      provideRouter([]),
      { provide: ArchiveApi, useValue: { lastTime } },
      { provide: AttachmentsApi, useValue: { quotes: quotesCall } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { view, lastTime, quotesCall };
}

describe('LastTimeBlockComponent', () => {
  it('shows "Letztes Mal" and, for an own edition, the quotes of the last time', async () => {
    const { quotesCall } = await setup();
    expect(await screen.findByRole('heading', { name: 'Letztes Mal' })).toBeInTheDocument();
    expect(screen.getByText(/245,00/)).toBeInTheDocument();
    expect(quotesCall).toHaveBeenCalledWith('tpl-1');
    expect(await screen.findByText('Beamer GmbH')).toBeInTheDocument();
  });

  it('asks for nothing without a template or a format', async () => {
    const { lastTime } = await setup(makeEvent());
    expect(lastTime).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: 'Letztes Mal' })).not.toBeInTheDocument();
  });

  it('asks for the quotes of an own edition only', async () => {
    const foreign = makeLastTime({ source: { ...makeLastTime().source, own: false }, restricted: true, costsCents: null, revenueCents: null });
    const { quotesCall } = await setup(makeEvent({ formatId: 'f1' }), jest.fn(() => of(foreign)));
    expect(await screen.findByRole('heading', { name: 'Letztes Mal' })).toBeInTheDocument();
    expect(quotesCall).not.toHaveBeenCalled();
  });

  it('leaves out the quotes panel when the answer is an error', async () => {
    await setup(undefined, undefined, jest.fn(() => throwError(() => new HttpErrorResponse({ status: 404 }))));
    expect(await screen.findByRole('heading', { name: 'Letztes Mal' })).toBeInTheDocument();
    expect(screen.queryByText('Angebote der letzten Auflage')).not.toBeInTheDocument();
  });

  it('shows nothing when there is no earlier edition (null) or the request fails', async () => {
    await setup(undefined, jest.fn(() => of(null)));
    expect(screen.queryByRole('heading', { name: 'Letztes Mal' })).not.toBeInTheDocument();
  });
});
