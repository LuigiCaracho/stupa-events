/** Spec for P04 Event-Detail: facts in Berlin time, state banner, buttons, share and copy, past note, 404. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { card, detail } from '../../../../../testing/public-fixtures';
import { answer, mountPublic, tick } from '../../../../../testing/public-harness';
import { EventPageComponent } from './event.component';

const URL = '/api/public/events/movienight';
const open = () => mountPublic(EventPageComponent, 'e/:slug', '/e/movienight');

function setNavigator(value: Partial<Navigator>): void {
  Object.defineProperty(window, 'navigator', { value, configurable: true });
}

describe('EventPageComponent', () => {
  const original = window.navigator;
  afterEach(() => setNavigator(original));

  it('shows title, Berlin time, place, organizer and the poster with size and credit', async () => {
    const h = await open();
    await answer(h, { [URL]: detail() });
    expect(
      screen.getByRole('heading', { level: 1, name: 'Movienight: Arrival' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Do., 22. Okt. 2026, 20:00 bis 22:00 Uhr')).toBeInTheDocument();
    expect(screen.getByText('Kinosaal 9-133')).toBeInTheDocument();
    expect(screen.getByText('Alteburgstraße 150, Reutlingen')).toBeInTheDocument();
    expect(screen.getByText('Studierendenparlament')).toBeInTheDocument();
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img).toHaveAttribute('width', '1200');
    expect(img).toHaveAttribute('fetchpriority', 'high');
    expect(screen.getByText('Foto: Beispiel')).toBeInTheDocument();
  });

  it('renders the description and links the categories', async () => {
    const h = await open();
    await answer(h, { [URL]: detail() });
    expect(screen.getByText('lange')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Kultur' })).toHaveAttribute('href', '/k/kultur');
  });

  it('downloads the single ICS and opens the ticket in a new tab without a referrer', async () => {
    const h = await open();
    await answer(h, { [URL]: detail() });
    const ics = screen.getByRole('link', { name: 'In Kalender' });
    expect(ics).toHaveAttribute('href', '/ics/e/movienight.ics');
    expect(ics).toHaveAttribute('download', 'movienight.ics');
    const ticket = screen.getByRole('link', { name: 'Ticket' });
    expect(ticket).toHaveAttribute('target', '_blank');
    expect(ticket).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('has no ticket button without a ticket link or with an unsafe one', async () => {
    const h = await open();
    await answer(h, { [URL]: detail({ ticketUrl: 'javascript:alert(1)' }) });
    expect(screen.queryByRole('link', { name: 'Ticket' })).not.toBeInTheDocument();
  });

  it('shows "Treffpunkt auf Anfrage" without a place', async () => {
    const h = await open();
    await answer(h, { [URL]: detail({ venue: null, venueText: null }) });
    expect(screen.getByText('Treffpunkt auf Anfrage')).toBeInTheDocument();
  });

  it('puts the cancelled state with its reason before the title', async () => {
    const h = await open();
    await answer(h, {
      [URL]: detail({
        status: 'cancelled',
        statusReason: { code: 'room', text: 'Raum nicht verfügbar' },
      }),
    });
    const banner = screen.getByText('Abgesagt: Raum nicht verfügbar');
    const title = screen.getByRole('heading', { level: 1 });
    expect(banner.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('says a postponed event has no new date yet', async () => {
    const h = await open();
    await answer(h, { [URL]: detail({ status: 'postponed' }) });
    expect(screen.getByText('Verschoben, neuer Termin folgt.')).toBeInTheDocument();
  });

  it('notes a past event and links the review', async () => {
    const h = await open();
    await answer(h, { [URL]: detail({ isPast: true }) });
    expect(screen.getByText(/Diese Veranstaltung ist vorbei/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zum Rückblick' })).toHaveAttribute(
      'href',
      '/rueckblick',
    );
  });

  it('lists more of the series', async () => {
    const h = await open();
    await answer(h, {
      [URL]: detail({ more: [card({ slug: 'zwei', title: 'Zweiter Teil', path: '/e/zwei' })] }),
    });
    expect(screen.getByRole('heading', { name: 'Mehr aus dieser Reihe' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zweiter Teil' })).toHaveAttribute('href', '/e/zwei');
  });

  it('shares through the share sheet when there is one', async () => {
    const share = jest.fn().mockResolvedValue(undefined);
    setNavigator({ share } as unknown as Navigator);
    const h = await open();
    await answer(h, { [URL]: detail() });
    await userEvent.click(screen.getByRole('button', { name: 'Teilen' }));
    expect(share).toHaveBeenCalledWith({
      title: 'Movienight: Arrival',
      url: `${window.location.origin}/e/movienight`,
    });
  });

  it('shows a readable link when neither sharing nor copying works', async () => {
    setNavigator({} as Navigator);
    const h = await open();
    await answer(h, { [URL]: detail() });
    await userEvent.click(screen.getByRole('button', { name: 'Teilen' }));
    await tick(h);
    expect(await screen.findByText(/Link konnte nicht kopiert werden/)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Link zu dieser Veranstaltung' })).toHaveValue(
      `${window.location.origin}/e/movienight`,
    );
  });

  it('answers 404 with one sentence and no detail', async () => {
    const h = await open();
    await answer(h, { [URL]: { status: 404, body: { status: 404, code: 'not_found' } } });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Diese Veranstaltung gibt es nicht oder sie ist nicht mehr verfügbar.',
    );
  });

  it('shows the reload note when the call fails', async () => {
    const h = await open();
    await answer(h, { [URL]: { status: 500, body: { status: 500 } } });
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const h = await open();
    await answer(h, { [URL]: detail({ more: [card({ slug: 'z', path: '/e/z' })] }) });
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
