import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen, waitFor } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { fakeApi, makeEvent, makeGuards } from '../../../../testing/event-fixtures';
import type { TransitionId } from '../api/event.models';
import { EventsApi } from '../api/events-api.service';
import { TransitionDialogComponent } from './transition-dialog.component';

const blocker = {
  code: 'image_required',
  field: null,
  severity: 'blocker' as const,
  messageKey: 'guards.image_required',
  fixAction: 'upload_poster' as const,
};
const warning = {
  ...blocker,
  code: 'start_in_past',
  severity: 'warning' as const,
  messageKey: 'guards.start_in_past',
  fixAction: null,
};
const fourEyes = { ...blocker, code: 'four_eyes', messageKey: 'guards.four_eyes', fixAction: null };

describe('TransitionDialogComponent', () => {
  async function setup(api = fakeApi(), transition: TransitionId = 'T02') {
    const done = jest.fn();
    const partial = jest.fn();
    const stale = jest.fn();
    const fix = jest.fn();
    const closed = jest.fn();
    const view = await render(TransitionDialogComponent, {
      inputs: { target: makeEvent({ state: 'in_review', rev: 7 }), transition },
      providers: [{ provide: EventsApi, useValue: api }],
      on: { done, partial, stale, fix, closed },
    });
    const toasts = () =>
      TestBed.inject(ToastService)
        .toasts()
        .map((t) => t.message);
    return { view, api, done, partial, stale, fix, closed, toasts };
  }

  it('titles the dialog with the transition and confirms with the revision as If-Match', async () => {
    const { api, done } = await setup();
    expect(await screen.findByRole('dialog', { name: 'Freigabe anfragen' })).toBeInTheDocument();
    expect(api.guards).toHaveBeenCalledWith('ev-1', 'T02');
    await userEvent.type(screen.getByLabelText(/Notiz/), ' bitte prüfen ');
    await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
    expect(api.transition).toHaveBeenCalledWith('ev-1', 'T02', { note: 'bitte prüfen' }, 7);
    expect(done).toHaveBeenCalled();
  });

  it('keeps the confirm button off with a visible reason while a blocker is open', async () => {
    const api = fakeApi({
      guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [blocker] }))),
    });
    const { fix } = await setup(api, 'T04');
    expect(await screen.findByText('Poster fehlt oder ist nicht freigegeben.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Noch nicht möglich');
    await userEvent.click(screen.getByRole('button', { name: 'Poster hochladen' }));
    expect(fix).toHaveBeenCalledWith(blocker);
  });

  it('names the four-eyes rule and keeps the button off', async () => {
    const api = fakeApi({
      guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [fourEyes] }))),
    });
    await setup(api, 'T04');
    expect(
      await screen.findByText(
        'Du hast dieses Event eingereicht. Eine andere Person muss freigeben.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  });

  it('needs the tick for a warning', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ reasons: [warning] }))) });
    await setup(api);
    const confirm = await screen.findByRole('button', { name: 'Bestätigen' });
    expect(confirm).toBeDisabled();
    await userEvent.click(await screen.findByLabelText('Ich habe die Hinweise gelesen.'));
    expect(confirm).toBeEnabled();
  });

  describe.each([
    ['T03', 'Was soll sich ändern?'],
    ['T06', 'Warum nimmst du die Freigabe zurück?'],
    ['T07', 'Warum nimmst du das Event offline?'],
    ['T10', 'Warum öffnest du es wieder?'],
    ['T11', 'Warum verwirfst du es?'],
  ] as const)('%s', (transition, label) => {
    it('asks for a note and refuses an empty one', async () => {
      const { api, done } = await setup(fakeApi(), transition);
      await screen.findByRole('button', { name: 'Bestätigen' });
      await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
      expect(screen.getByText('Bitte gib einen Grund an.')).toBeInTheDocument();
      expect(api.transition).not.toHaveBeenCalled();
      await userEvent.type(screen.getByLabelText(new RegExp(label.replace('?', '\\?'))), 'weil');
      await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenCalledWith('ev-1', transition, { note: 'weil' }, 7);
      expect(done).toHaveBeenCalled();
    });
  });

  it('refuses a note over 500 characters', async () => {
    const { api } = await setup();
    await screen.findByRole('button', { name: 'Bestätigen' });
    await userEvent.click(screen.getByLabelText(/Notiz/));
    await userEvent.paste('x'.repeat(501));
    expect(screen.getByText(/zu lang/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
    expect(api.transition).not.toHaveBeenCalled();
  });

  describe('T04', () => {
    it('publishes at once by a second call after the approval', async () => {
      const approved = makeEvent({ state: 'approved', rev: 8 });
      const live = makeEvent({ state: 'live', rev: 9 });
      const api = fakeApi({
        transition: jest.fn().mockReturnValueOnce(of(approved)).mockReturnValueOnce(of(live)),
      });
      const { done } = await setup(api, 'T04');
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenNthCalledWith(1, 'ev-1', 'T04', {}, 7);
      expect(api.transition).toHaveBeenNthCalledWith(2, 'ev-1', 'T05', {}, 8);
      expect(done).toHaveBeenCalledWith(live);
    });

    it('sets the release time and leaves the publishing to the worker', async () => {
      const api = fakeApi({
        transition: jest.fn(() => of(makeEvent({ state: 'approved', rev: 8 }))),
      });
      const { done } = await setup(api, 'T04');
      await screen.findByRole('button', { name: 'Bestätigen' });
      await userEvent.click(screen.getByRole('switch', { name: 'Sofort veröffentlichen' }));
      await waitFor(() => expect(screen.getByLabelText(/Veröffentlichen am, Datum/)).toBeEnabled());
      await userEvent.type(screen.getByLabelText(/Veröffentlichen am, Datum/), '01.11.2099');
      await userEvent.tab();
      await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
      expect(screen.getByText('Bitte wähle Datum und Uhrzeit.')).toBeInTheDocument();
      expect(api.transition).not.toHaveBeenCalled();
      await userEvent.type(screen.getByLabelText(/Veröffentlichen am, Uhrzeit/), '10:00');
      await userEvent.tab();
      await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenCalledTimes(1);
      expect(api.transition).toHaveBeenCalledWith(
        'ev-1',
        'T04',
        { publishAt: '2099-11-01T09:00:00Z' },
        7,
      );
      expect(done).toHaveBeenCalled();
    });

    it('only approves when the switch is off and no time is set', async () => {
      const api = fakeApi({
        transition: jest.fn(() => of(makeEvent({ state: 'approved', rev: 8 }))),
      });
      const { done } = await setup(api, 'T04');
      await screen.findByRole('button', { name: 'Bestätigen' });
      await userEvent.click(screen.getByRole('switch', { name: 'Sofort veröffentlichen' }));
      await userEvent.click(screen.getByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenCalledTimes(1);
      expect(api.transition).toHaveBeenCalledWith('ev-1', 'T04', {}, 7);
      expect(done).toHaveBeenCalled();
    });

    it('says that the event stays approved when the follow-up publishing fails', async () => {
      const approved = makeEvent({ state: 'approved', rev: 8 });
      const refused = new HttpErrorResponse({
        status: 422,
        error: { status: 422, reasons: [{ ...blocker }] },
      });
      const api = fakeApi({
        transition: jest
          .fn()
          .mockReturnValueOnce(of(approved))
          .mockReturnValueOnce(throwError(() => refused)),
      });
      const { done, partial } = await setup(api, 'T04');
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(partial).toHaveBeenCalledWith(approved);
      expect(done).not.toHaveBeenCalled();
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Freigegeben, aber noch nicht veröffentlicht: Nicht möglich: Poster fehlt',
      );
      expect(screen.queryByRole('button', { name: 'Bestätigen' })).not.toBeInTheDocument();
    });
  });

  it('names the state when another transition was faster', async () => {
    const current = makeEvent({ state: 'approved' });
    const conflict = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'conflict', current },
    });
    const { stale, toasts } = await setup(
      fakeApi({ transition: jest.fn(() => throwError(() => conflict)) }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    expect(stale).toHaveBeenCalledWith(current);
    expect(toasts()).toEqual([
      'Ein anderer Übergang war schneller. Zustand ist jetzt: Freigegeben.',
    ]);
  });

  it('uses the plain conflict text without the current version', async () => {
    const conflict = new HttpErrorResponse({
      status: 409,
      error: { status: 409, code: 'conflict' },
    });
    const { stale, toasts } = await setup(
      fakeApi({ transition: jest.fn(() => throwError(() => conflict)) }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    expect(stale).toHaveBeenCalledWith(null);
    expect(toasts()[0]).toContain('Jemand anderes');
  });

  it('reads the guards again after a refusal', async () => {
    const refused = new HttpErrorResponse({
      status: 422,
      error: { status: 422, code: 'image_required', reasons: [blocker] },
    });
    const api = fakeApi({ transition: jest.fn(() => throwError(() => refused)) });
    await setup(api);
    await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
    await waitFor(() => expect(api.guards).toHaveBeenCalledTimes(2));
  });

  it('keeps the confirm button off when the role may not fire the transition', async () => {
    const forbidden = {
      ...blocker,
      code: 'forbidden',
      messageKey: 'guards.forbidden',
      fixAction: null,
    };
    const api = fakeApi({
      guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [forbidden] }))),
    });
    await setup(api, 'T04');
    expect(await screen.findByText('Dafür fehlt dir die Berechtigung.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  });

  it('keeps the confirm button off when the server says not allowed without a reason', async () => {
    const api = fakeApi({ guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [] }))) });
    await setup(api, 'T04');
    expect(await screen.findByText(/Noch nicht möglich/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeDisabled();
  });

  it('tells the cause when the guards cannot be read and retries on request', async () => {
    const offline = new HttpErrorResponse({ status: 0 });
    const api = fakeApi({
      guards: jest
        .fn()
        .mockReturnValueOnce(throwError(() => offline))
        .mockReturnValue(of(makeGuards())),
    });
    await setup(api);
    expect(await screen.findByRole('alert')).toHaveTextContent('Keine Verbindung');
    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Bestätigen' })).toBeEnabled());
    expect(api.guards).toHaveBeenCalledTimes(2);
  });

  it('closes from the cancel button and has no axe violations', async () => {
    const { closed, view } = await setup(fakeApi(), 'T04');
    await screen.findByRole('button', { name: 'Bestätigen' });
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
    view.fixture.destroy();
  });
});
