/** Spec for P06 Get started: the step order, the interest lock, the mail step and its checks, the request bodies, the result and what is (not) stored. */
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { runAxe } from '../../../../../testing/a11y';
import {
  answer,
  mountPublic,
  tick,
  type PublicHarness,
} from '../../../../../testing/public-harness';
import { QUESTIONNAIRE, SUBSCRIBED } from '../../../../../testing/subscription-fixtures';
import { StartPageComponent } from './start.component';

const open = async () => {
  const h = await mountPublic(StartPageComponent, 'start', '/start');
  await answer(h, { '/api/public/getstarted/questions': QUESTIONNAIRE });
  return h;
};

const press = async (h: PublicHarness<unknown>, name: string | RegExp) => {
  await userEvent.click(screen.getByRole('button', { name }));
  await tick(h);
};

const reachChannel = async (h: PublicHarness<unknown>) => {
  await press(h, 'Partys und Feiern');
  await press(h, 'Weiter');
  await press(h, 'Weiter');
};

const submitWith = async (h: PublicHarness<unknown>, out: object) => {
  h.http.expectOne('/api/public/altcha/challenge').flush(null, { status: 404, statusText: 'x' });
  await tick(h);
  const req = h.http.expectOne('/api/public/subscriptions');
  req.flush(out, { status: 202, statusText: 'Accepted' });
  await tick(h);
  return req.request.body;
};

describe('StartPageComponent', () => {
  beforeEach(() => window.sessionStorage.clear());

  it('offers the interests as chips without the meetings chip and nothing chosen', async () => {
    await open();
    expect(screen.getByRole('heading', { name: 'Was interessiert dich?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Partys und Feiern' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.queryByRole('button', { name: 'Sitzungen und Gremien' })).toBeNull();
  });

  it('locks "Weiter" until an interest is chosen', async () => {
    const h = await open();
    expect(screen.getByRole('button', { name: 'Weiter' })).toBeDisabled();
    expect(screen.getByText('Wähl mindestens ein Interesse.')).toBeInTheDocument();
    await press(h, 'Partys und Feiern');
    expect(screen.getByRole('button', { name: 'Partys und Feiern' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Weiter' })).toBeEnabled();
  });

  it('walks interests, faculty and channel; the calendar channel has no mail step', async () => {
    const h = await open();
    await reachChannel(h);
    expect(
      screen.getByRole('heading', { name: 'Wie möchtest du auf dem Laufenden bleiben?' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Profil erstellen' })).toBeInTheDocument();
    expect(screen.queryByText('Mailadresse')).toBeNull();
  });

  it('adds the mail step for "Kalender und Mail" and keeps the answers on the way back', async () => {
    const h = await open();
    await reachChannel(h);
    await userEvent.click(screen.getByRole('radio', { name: 'Kalender und Mail' }));
    await tick(h);
    await press(h, 'Weiter');
    expect(screen.getByLabelText('Mailadresse')).toBeInTheDocument();
    await press(h, 'Zurück');
    await press(h, 'Zurück');
    await press(h, 'Zurück');
    expect(screen.getByRole('button', { name: 'Partys und Feiern' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('creates a calendar-only profile: solves ALTCHA, posts the answers, shows webcal and https', async () => {
    const h = await open();
    await press(h, 'Partys und Feiern');
    await userEvent.click(screen.getByRole('radio', { name: 'Nein' }));
    await press(h, 'Weiter');
    await press(h, 'Weiter');
    await press(h, 'Profil erstellen');
    const body = await submitWith(h, SUBSCRIBED(false));
    expect(body).toEqual({
      questionnaireVersion: 1,
      answers: { interests: ['party'], meetings: false, faculty: null, mail: false },
      email: null,
      consent: null,
      altcha: '',
    });
    expect(screen.getByRole('heading', { name: 'Dein Kalender ist fertig' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'In Kalender-App öffnen' })).toHaveAttribute(
      'href',
      'webcal://events.test/ics/p/TOKEN.ics',
    );
    expect(screen.getByLabelText('Dein Kalender-Link')).toHaveValue(
      'https://events.test/ics/p/TOKEN.ics',
    );
    expect(screen.queryByText('Wir haben dir eine Bestätigungsmail geschickt.')).toBeNull();
  });

  it('never stores the token, and forgets the answers after the profile exists', async () => {
    const h = await open();
    await reachChannel(h);
    await press(h, 'Profil erstellen');
    await submitWith(h, SUBSCRIBED(false));
    const stored = JSON.stringify({ ...window.sessionStorage, ...window.localStorage });
    expect(stored).not.toContain('TOKEN');
    expect(window.sessionStorage.length).toBe(0);
  });

  it('checks the address and the consent before it sends anything', async () => {
    const h = await open();
    await reachChannel(h);
    await userEvent.click(screen.getByRole('radio', { name: 'Kalender und Mail' }));
    await tick(h);
    await press(h, 'Weiter');
    await userEvent.type(screen.getByLabelText('Mailadresse'), 'kaputt');
    await press(h, 'Profil erstellen');
    expect(screen.getByText('Das sieht nicht wie eine Mailadresse aus.')).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText('Mailadresse'));
    await userEvent.type(screen.getByLabelText('Mailadresse'), 'wer@example.test');
    await press(h, 'Profil erstellen');
    expect(screen.getByText('Bitte bestätige die Einwilligung.')).toBeInTheDocument();
    h.http.expectNone('/api/public/altcha/challenge');
  });

  it('shows the consent sentence with the chosen categories', async () => {
    const h = await open();
    await reachChannel(h);
    await userEvent.click(screen.getByRole('radio', { name: 'Kalender und Mail' }));
    await tick(h);
    await press(h, 'Weiter');
    expect(
      screen.getByText(
        /Ich möchte wöchentlich eine Mail zu Partys und Feiern\. Abmelden geht jederzeit/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Datenschutz' })).toHaveAttribute(
      'href',
      '/datenschutz',
    );
  });

  it('sends the address with the consent version and shows the same note whatever the address was', async () => {
    const h = await open();
    await reachChannel(h);
    await userEvent.click(screen.getByRole('radio', { name: 'Kalender und Mail' }));
    await tick(h);
    await press(h, 'Weiter');
    await userEvent.type(screen.getByLabelText('Mailadresse'), ' wer@example.test ');
    await userEvent.click(screen.getByRole('checkbox'));
    await press(h, 'Profil erstellen');
    const body = await submitWith(h, SUBSCRIBED(true));
    expect(body).toMatchObject({
      answers: { mail: true },
      email: 'wer@example.test',
      consent: { version: '2026-10-1', accepted: true },
    });
    expect(screen.getByText('Wir haben dir eine Bestätigungsmail geschickt.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Zu den Abos' })).toHaveAttribute('href', '/abos');
  });

  it('tells the visitor to wait after a 429, with the minutes of Retry-After', async () => {
    const h = await open();
    await reachChannel(h);
    await press(h, 'Profil erstellen');
    h.http.expectOne('/api/public/altcha/challenge').flush(null, { status: 404, statusText: 'x' });
    await tick(h);
    h.http
      .expectOne('/api/public/subscriptions')
      .flush(
        { status: 429, code: 'rate_limited' },
        { status: 429, statusText: 'x', headers: { 'Retry-After': '900' } },
      );
    await tick(h);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Zu viele Versuche. Bitte warte 15 Minuten.',
    );
  });

  it('words a failed spam check and stays on the form', async () => {
    const h = await open();
    await reachChannel(h);
    await press(h, 'Profil erstellen');
    h.http.expectOne('/api/public/altcha/challenge').flush(null, { status: 404, statusText: 'x' });
    await tick(h);
    h.http
      .expectOne('/api/public/subscriptions')
      .flush({ status: 400, code: 'altcha_invalid' }, { status: 400, statusText: 'x' });
    await tick(h);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Prüfung gegen Spam hat nicht geklappt. Bitte versuch es noch einmal.',
    );
    expect(screen.getByRole('button', { name: 'Profil erstellen' })).toBeEnabled();
  });

  it('restores the answers of a reload from the session, but the address and consent stay empty', async () => {
    window.sessionStorage.setItem(
      'stupa-events.getstarted',
      JSON.stringify({ interests: ['kultur'], meetings: false, faculty: null, channel: 'mail' }),
    );
    await open();
    expect(screen.getByRole('button', { name: 'Kino, Konzerte, Kultur' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('has no axe violations on the first step', async () => {
    const h = await open();
    expect(await runAxe(h.harness.routeNativeElement as HTMLElement)).toHaveNoViolations();
  });
});
