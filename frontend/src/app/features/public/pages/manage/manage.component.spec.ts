/** Spec for P09 Abo verwalten: the load with the token header, saving interests, the mail switch, the new calendar address with its question, deleting with a dialog, the invalid link. */
import { Location } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import { mountPublic, tick, type PublicHarness } from '../../../../../testing/public-harness';
import { ME, QUESTIONNAIRE } from '../../../../../testing/subscription-fixtures';
import { ManagePageComponent } from './manage.component';

const ME_URL = '/api/public/subscriptions/me';

const open = async (me: object | { status: number } = ME) => {
  const h = await mountPublic(ManagePageComponent, 'abo/:token', '/abo/tok-xyz');
  const req = h.http.expectOne(ME_URL);
  expect(req.request.headers.get('X-Subscription-Token')).toBe('tok-xyz');
  expect(req.request.url).not.toContain('tok-xyz');
  if ('status' in me)
    req.flush({ status: 404, code: 'invalid_token' }, { status: 404, statusText: 'x' });
  else req.flush(me);
  h.http.expectOne('/api/public/getstarted/questions').flush(QUESTIONNAIRE);
  await tick(h);
  await tick(h);
  return h;
};

const press = async (h: PublicHarness<unknown>, name: string | RegExp) => {
  await userEvent.click(screen.getByRole('button', { name }));
  await tick(h);
};

describe('ManagePageComponent', () => {
  it('loads the subscription with the token in a header and takes the token out of the address bar', async () => {
    await open();
    expect(screen.getByRole('button', { name: 'Partys und Feiern' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Fachschaft FSI' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
    expect(TestBed.inject(Location).path()).toBe('/abo');
  });

  it('saves changed interests with the faculty folded back in', async () => {
    const h = await open();
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled();
    await press(h, 'Kino, Konzerte, Kultur');
    await press(h, 'Speichern');
    const req = h.http.expectOne(ME_URL);
    expect(req.request.method).toBe('PUT');
    expect(req.request.body).toEqual({ interests: ['party', 'kultur', 'fachschaft:fsi'] });
    expect(req.request.headers.get('X-Subscription-Token')).toBe('tok-xyz');
    req.flush({ ...ME, interests: ['party', 'kultur', 'fachschaft:fsi'] });
    await tick(h);
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled();
  });

  it('does not let the last interest go', async () => {
    const h = await open();
    await press(h, 'Partys und Feiern');
    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled();
    expect(screen.getByText('Wähl mindestens ein Interesse.')).toBeInTheDocument();
  });

  it('switches the mail off', async () => {
    const h = await open();
    await userEvent.click(screen.getByRole('switch'));
    const req = h.http.expectOne(ME_URL);
    expect(req.request.body).toEqual({ mailEnabled: false });
    req.flush({ ...ME, mailEnabled: false });
    await tick(h);
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false');
  });

  it('asks before it makes a new calendar address and shows it once', async () => {
    const h = await open();
    await press(h, 'Neue URL erzeugen');
    const dialog = screen.getByRole('dialog');
    expect(
      within(dialog).getByText('Der alte Link hört dann auf zu funktionieren.'),
    ).toBeInTheDocument();
    h.http.expectNone(`${ME_URL}/ics-token`);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Neue URL erzeugen' }));
    h.http.expectOne(`${ME_URL}/ics-token`).flush({
      icsUrl: 'https://events.test/ics/p/NEW.ics',
      webcalUrl: 'webcal://events.test/ics/p/NEW.ics',
    });
    await tick(h);
    expect(screen.getByLabelText('Dein Kalender-Link')).toHaveValue(
      'https://events.test/ics/p/NEW.ics',
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('has no calendar card without a profile', async () => {
    await open({ ...ME, hasProfile: false });
    expect(screen.queryByRole('button', { name: 'Neue URL erzeugen' })).toBeNull();
  });

  it('deletes everything only after the dialog', async () => {
    const h = await open();
    await press(h, 'Alles abbestellen und Daten löschen');
    h.http.expectNone(ME_URL);
    const dialog = screen.getByRole('dialog');
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Alles abbestellen und Daten löschen' }),
    );
    const req = h.http.expectOne(ME_URL);
    expect(req.request.method).toBe('DELETE');
    req.flush(null, { status: 204, statusText: 'No Content' });
    await tick(h);
    expect(
      screen.getByText('Erledigt. Wir haben deine Adresse und dein Profil gelöscht.'),
    ).toBeInTheDocument();
  });

  it('shows the invalid-link state with a field for a new link', async () => {
    await open({ status: 404 });
    expect(screen.getByText('Dieser Verwaltungslink ist ungültig.')).toBeInTheDocument();
    expect(screen.getByLabelText('Mailadresse')).toBeInTheDocument();
  });

  it('turns invalid when a save answers 404 (the link ran out meanwhile)', async () => {
    const h = await open();
    await press(h, 'Kino, Konzerte, Kultur');
    await press(h, 'Speichern');
    h.http
      .expectOne(ME_URL)
      .flush({ status: 404, code: 'invalid_token' }, { status: 404, statusText: 'x' });
    await tick(h);
    expect(screen.getByText('Dieser Verwaltungslink ist ungültig.')).toBeInTheDocument();
  });

  it('has no axe violations', async () => {
    const h = await open();
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
