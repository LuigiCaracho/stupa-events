/** Spec for P08 Bestätigen: the preview changes nothing, the button posts, the unusable token has one sentence, the token leaves the address bar. */
import { Location } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { mountPublic, tick, type PublicHarness } from '../../../../../testing/public-harness';
import { ConfirmPageComponent } from './confirm.component';

const PREVIEW = '/api/public/subscriptions/confirm/preview';
const CONFIRM = '/api/public/subscriptions/confirm';

const open = async (preview: object | { status: number } = { categories: ['Party', 'Kino'] }) => {
  const h = await mountPublic(ConfirmPageComponent, 'bestaetigen/:token', '/bestaetigen/tok-abc');
  const req = h.http.expectOne(PREVIEW);
  expect(req.request.body).toEqual({ token: 'tok-abc' });
  if ('status' in preview)
    req.flush({ status: 404, code: 'invalid_token' }, { status: 404, statusText: 'x' });
  else req.flush(preview);
  await tick(h);
  await tick(h);
  return h;
};

describe('ConfirmPageComponent', () => {
  it('shows the categories and confirms nothing by itself', async () => {
    const h = await open();
    expect(screen.getByText('Du willst Mails zu Party und Kino bekommen.')).toBeInTheDocument();
    h.http.expectNone(CONFIRM);
    expect(screen.getByRole('button', { name: 'Abo bestätigen' })).toBeEnabled();
  });

  it('posts the token with the button and thanks', async () => {
    const h = await open();
    await userEvent.click(screen.getByRole('button', { name: 'Abo bestätigen' }));
    const req = h.http.expectOne(CONFIRM);
    expect(req.request.body).toEqual({ token: 'tok-abc' });
    req.flush({ status: 'confirmed' });
    await tick(h);
    expect(screen.getByText('Danke, dein Abo ist aktiv.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zu den Abos' })).toHaveAttribute('href', '/abos');
  });

  it('says the same sentence for an expired, used or unknown link and offers a new signup', async () => {
    await open({ status: 404 });
    expect(
      screen.getByText('Dieser Link ist abgelaufen oder wurde schon benutzt.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Neu anmelden' })).toHaveAttribute('href', '/start');
    expect(screen.queryByRole('button', { name: 'Abo bestätigen' })).toBeNull();
  });

  it('turns to the invalid sentence when the confirm itself answers 404', async () => {
    const h = await open();
    await userEvent.click(screen.getByRole('button', { name: 'Abo bestätigen' }));
    h.http
      .expectOne(CONFIRM)
      .flush({ status: 404, code: 'invalid_token' }, { status: 404, statusText: 'x' });
    await tick(h);
    expect(
      screen.getByText('Dieser Link ist abgelaufen oder wurde schon benutzt.'),
    ).toBeInTheDocument();
  });

  it('removes the token from the address bar after the check', async () => {
    await open();
    expect(TestBed.inject(Location).path()).toBe('/bestaetigen');
  });

  it('has no axe violations', async () => {
    const h: PublicHarness<ConfirmPageComponent> = await open();
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
