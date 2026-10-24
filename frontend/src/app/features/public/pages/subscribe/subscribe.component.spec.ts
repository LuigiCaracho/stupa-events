/** Spec for P07 Abos: addresses, webcal links, copy with and without the clipboard, the anchor, the instructions. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { CATEGORIES } from '../../../../../testing/public-fixtures';
import { answer, mountPublic, tick } from '../../../../../testing/public-harness';
import { SubscribePageComponent } from './subscribe.component';

const open = async (url = '/abos', categories: object = CATEGORIES) => {
  const h = await mountPublic(SubscribePageComponent, 'abos', url);
  await answer(h, { '/api/public/categories': categories });
  return h;
};

function setNavigator(value: Partial<Navigator>): void {
  Object.defineProperty(window, 'navigator', { value, configurable: true });
}

describe('SubscribePageComponent', () => {
  const original = window.navigator;
  const origin = window.location.origin;
  afterEach(() => setNavigator(original));

  it('warns about the delay and offers the all-in-one calendar as webcal and https', async () => {
    await open();
    expect(screen.getByText(/Änderungen kommen mit Verzögerung an/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'In Kalender-App öffnen' })).toHaveAttribute(
      'href',
      `${origin.replace(/^https?:/, 'webcal:')}/ics/all.ics`,
    );
    expect(screen.getByText(`${origin}/ics/all.ics`)).toBeInTheDocument();
  });

  it('lists a calendar per category with the full address', async () => {
    await open();
    expect(screen.getByRole('heading', { name: 'Party' })).toBeInTheDocument();
    expect(screen.getByText(`${origin}/ics/k/party.ics`)).toBeInTheDocument();
    const links = screen.getAllByRole('link', { name: 'Kalender öffnen' });
    expect(links[1]).toHaveAttribute(
      'href',
      `${origin.replace(/^https?:/, 'webcal:')}/ics/k/party.ics`,
    );
  });

  it('marks the row of the anchor', async () => {
    await open('/abos#k=party');
    expect(document.getElementById('k-party')).toHaveClass('sub__row--marked');
    expect(document.getElementById('k-kultur')).not.toHaveClass('sub__row--marked');
  });

  it('copies the https address', async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    setNavigator({ clipboard: { writeText } } as unknown as Navigator);
    await open();
    await userEvent.click(screen.getByRole('button', { name: 'Adresse von Party kopieren' }));
    expect(writeText).toHaveBeenCalledWith(`${origin}/ics/k/party.ics`);
  });

  it('tells the visitor to mark the address by hand when copying fails', async () => {
    setNavigator({} as Navigator);
    const h = await open();
    await userEvent.click(screen.getAllByRole('button', { name: 'Kopieren' })[0]);
    await tick(h);
    expect(screen.getByRole('alert')).toHaveTextContent('Markier die Adresse bitte von Hand.');
  });

  it('points to Get started and says that mail needs a confirmation', async () => {
    await open();
    expect(
      screen.getByRole('heading', { name: 'Persönlich: Interessen wählen' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Get started' })).toHaveAttribute('href', '/start');
    expect(screen.getByText('Mail-Abo gibt es nur mit Bestätigung.')).toBeInTheDocument();
  });

  it('asks for the manage link in a dialog and shows the same sentence whatever the address', async () => {
    const h = await open();
    await userEvent.click(screen.getByRole('button', { name: 'Verwaltungslink anfordern' }));
    await tick(h);
    await userEvent.type(screen.getByLabelText('Mailadresse'), 'wer@example.test');
    await userEvent.click(screen.getByRole('button', { name: 'Link anfordern' }));
    h.http.expectOne('/api/public/altcha/challenge').flush(null, { status: 404, statusText: 'x' });
    await tick(h);
    await tick(h);
    const req = h.http.expectOne('/api/public/subscriptions/manage-link');
    expect(req.request.body).toEqual({ email: 'wer@example.test', altcha: '' });
    req.flush({}, { status: 202, statusText: 'Accepted' });
    await tick(h);
    expect(
      screen.getByText('Wenn die Adresse bei uns angemeldet ist, ist der Link unterwegs.'),
    ).toBeInTheDocument();
  });

  it('does not send a malformed address', async () => {
    const h = await open();
    await userEvent.click(screen.getByRole('button', { name: 'Verwaltungslink anfordern' }));
    await tick(h);
    await userEvent.type(screen.getByLabelText('Mailadresse'), 'kaputt');
    await userEvent.click(screen.getByRole('button', { name: 'Link anfordern' }));
    await tick(h);
    expect(screen.getByText('Das sieht nicht wie eine Mailadresse aus.')).toBeInTheDocument();
    h.http.expectNone('/api/public/altcha/challenge');
  });

  it('explains Google, Apple and Thunderbird', async () => {
    await open();
    for (const name of ['Google Kalender', 'Apple Kalender', 'Thunderbird']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
  });

  it('has no axe violations', async () => {
    const h = await open();
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
