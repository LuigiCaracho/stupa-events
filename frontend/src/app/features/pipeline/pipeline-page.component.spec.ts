import { HttpErrorResponse } from '@angular/common/http';
import { Router, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../testing/a11y';
import {
  fakeApi,
  makeCard,
  makeColumn,
  makeEvent,
  makeGuards,
} from '../../../testing/event-fixtures';
import { EventsApi } from '../dossiers/api/events-api.service';
import { PipelinePageComponent } from './pipeline-page.component';

const idea = makeCard({
  id: 'c-idea',
  title: 'Idee A',
  state: 'idea',
  moves: { planning: 'T01' },
  allowedTransitions: ['T01'],
  rev: 5,
});
const planning = makeCard({
  id: 'c-plan',
  title: 'Plan B',
  moves: { in_review: 'T02' },
  allowedTransitions: ['T02', 'T11'],
});

const board = (...cols: ReturnType<typeof makeColumn>[]) =>
  of({ columns: cols, generatedAt: '2026-10-18T10:00:00Z' });

const withCards = () =>
  board(
    makeColumn('idea', [idea]),
    makeColumn('planning', [planning]),
    makeColumn('in_review'),
    makeColumn('published'),
    makeColumn('followup'),
  );

function phoneMedia(phone: boolean): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: phone && query.includes('max-width: 768px'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  });
}

async function setup(api = fakeApi({ board: jest.fn(withCards) }), fakeTimers = false) {
  const view = await render(PipelinePageComponent, {
    providers: [provideRouter([]), { provide: EventsApi, useValue: api }],
  });
  view.fixture.detectChanges();
  if (fakeTimers) await jest.advanceTimersByTimeAsync(0);
  else await view.fixture.whenStable();
  view.fixture.detectChanges();
  const router = TestBed.inject(Router);
  const navigate = jest.spyOn(router, 'navigate').mockResolvedValue(true);
  const navigateByUrl = jest.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
  const toasts = () =>
    TestBed.inject(ToastService)
      .toasts()
      .map((t) => t.message);
  const live = () => {
    view.fixture.detectChanges();
    return view.container.querySelector('[aria-live]')?.textContent?.trim() ?? '';
  };
  return { view, api, navigate, navigateByUrl, toasts, live };
}

describe('PipelinePageComponent', () => {
  afterEach(() => {
    phoneMedia(false);
    jest.useRealTimers();
  });

  it('loads the board with the column limit and shows the cards', async () => {
    const { api } = await setup();
    expect(api.board).toHaveBeenCalledWith(expect.objectContaining({ columnLimit: 50 }));
    expect(screen.getByRole('heading', { name: 'Pipeline' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Idee A/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Plan B/ })).toBeInTheDocument();
  });

  it('opens the dossier when a card is clicked', async () => {
    const { navigate } = await setup();
    await userEvent.click(screen.getByRole('button', { name: /Plan B/ }));
    expect(navigate).toHaveBeenCalledWith(['/dossiers', 'c-plan']);
  });

  it('offers the list and a new event', async () => {
    const { navigateByUrl } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Liste' }));
    expect(navigateByUrl).toHaveBeenLastCalledWith('/dossiers');
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' })[0]);
    expect(navigateByUrl).toHaveBeenLastCalledWith('/dossiers/neu');
  });

  it('shows the empty state with the first-event button when there is nothing at all', async () => {
    const { navigateByUrl } = await setup(
      fakeApi({
        board: jest.fn(() =>
          board(makeColumn('idea'), makeColumn('planning'), makeColumn('in_review')),
        ),
      }),
    );
    expect(screen.getByText('Noch keine Events. Leg das erste an.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' }).at(-1)!);
    expect(navigateByUrl).toHaveBeenCalledWith('/dossiers/neu');
  });

  it('shows an error note with a retry when the load fails', async () => {
    const { api } = await setup(
      fakeApi({ board: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Die Pipeline konnte nicht geladen werden.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
    expect(api.board).toHaveBeenCalledTimes(2);
  });

  describe('moves', () => {
    it('fires T01 at once by keyboard, announces it and reloads the board', async () => {
      const { api, live } = await setup();
      screen.getByRole('button', { name: /Idee A/ }).focus();
      await userEvent.setup().keyboard(' {ArrowRight} ');
      expect(api.transition).toHaveBeenCalledWith('c-idea', 'T01', {}, 5);
      expect(live()).toBe('„Movienight“ nach Freigabe verschoben.');
      expect(api.board).toHaveBeenCalledTimes(2);
    });

    it('tells the reasons when the server refuses T01 and reloads on a stale card', async () => {
      const refused = new HttpErrorResponse({
        status: 422,
        error: {
          status: 422,
          reasons: [
            {
              code: 'x',
              field: 'title',
              severity: 'blocker',
              messageKey: 'guards.field_missing',
              fixAction: 'fill_field',
            },
          ],
        },
      });
      const stale = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'conflict' },
      });
      const offline = new HttpErrorResponse({ status: 500 });
      const api = fakeApi({
        board: jest.fn(withCards),
        transition: jest
          .fn()
          .mockReturnValueOnce(throwError(() => refused))
          .mockReturnValueOnce(throwError(() => stale))
          .mockReturnValueOnce(throwError(() => offline)),
      });
      const { toasts } = await setup(api);
      const user = userEvent.setup();
      for (let i = 0; i < 3; i++) {
        screen.getByRole('button', { name: /Idee A/ }).focus();
        await user.keyboard(' {ArrowRight} ');
      }
      expect(toasts()[0]).toBe('Verschieben nicht möglich: Es fehlt: Titel.');
      expect(toasts()[1]).toBe('Diese Karte wurde inzwischen geändert. Board neu geladen.');
      expect(toasts()[2]).toContain('Das hat nicht geklappt');
      expect(api.board).toHaveBeenCalledTimes(4);
    });

    it('opens the confirmation for a move into the review and applies the result', async () => {
      const api = fakeApi({
        board: jest.fn(withCards),
        guards: jest.fn(() => of(makeGuards({ allowed: true }))),
        transition: jest.fn(() => of(makeEvent({ state: 'in_review' }))),
      });
      const { live } = await setup(api);
      screen.getByRole('button', { name: /Plan B/ }).focus();
      await userEvent.setup().keyboard(' {ArrowRight} ');
      expect(await screen.findByRole('dialog', { name: 'Freigabe anfragen' })).toBeInTheDocument();
      expect(api.guards).toHaveBeenCalledWith('c-plan', 'T02');
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(api.transition).toHaveBeenCalledWith('c-plan', 'T02', {}, 3);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(live()).toContain('nach Freigabe verschoben');
    });

    it('reloads with a note when the dialog meets a stale card', async () => {
      const stale = new HttpErrorResponse({
        status: 409,
        error: { status: 409, code: 'conflict' },
      });
      const api = fakeApi({
        board: jest.fn(withCards),
        transition: jest.fn(() => throwError(() => stale)),
      });
      const { toasts } = await setup(api);
      screen.getByRole('button', { name: /Plan B/ }).focus();
      await userEvent.setup().keyboard(' {ArrowRight} ');
      await userEvent.click(await screen.findByRole('button', { name: 'Bestätigen' }));
      expect(toasts()).toContain('Diese Karte wurde inzwischen geändert. Board neu geladen.');
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(api.board).toHaveBeenCalledTimes(2);
    });

    it('goes to the dossier from a fix button of the dialog', async () => {
      const blocker = {
        code: 'image_required',
        field: null,
        severity: 'blocker' as const,
        messageKey: 'guards.image_required',
        fixAction: 'upload_poster' as const,
      };
      const api = fakeApi({
        board: jest.fn(withCards),
        guards: jest.fn(() => of(makeGuards({ allowed: false, reasons: [blocker] }))),
      });
      const { navigate } = await setup(api);
      screen.getByRole('button', { name: /Plan B/ }).focus();
      await userEvent.setup().keyboard(' {ArrowRight} ');
      await userEvent.click(await screen.findByRole('button', { name: 'Poster hochladen' }));
      expect(navigate).toHaveBeenCalledWith(['/dossiers', 'c-plan']);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('refresh', () => {
    it('reloads every 60 seconds and on window focus, but not while a card is held', async () => {
      jest.useFakeTimers();
      const { api, view } = await setup(undefined, true);
      await jest.advanceTimersByTimeAsync(60_000);
      view.fixture.detectChanges();
      await jest.advanceTimersByTimeAsync(0);
      expect(api.board).toHaveBeenCalledTimes(2);
      document.dispatchEvent(new Event('visibilitychange'));
      view.fixture.detectChanges();
      await jest.advanceTimersByTimeAsync(0);
      expect(api.board).toHaveBeenCalledTimes(3);
      view.fixture.detectChanges();
      screen.getByRole('button', { name: /Idee A/ }).focus();
      await userEvent.setup({ advanceTimers: jest.advanceTimersByTime }).keyboard(' ');
      await jest.advanceTimersByTimeAsync(120_000);
      view.fixture.detectChanges();
      expect(api.board).toHaveBeenCalledTimes(3);
    });

    it('skips the reload while the tab is hidden', async () => {
      jest.useFakeTimers();
      const { api, view } = await setup(undefined, true);
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
      await jest.advanceTimersByTimeAsync(60_000);
      view.fixture.detectChanges();
      Reflect.deleteProperty(document, 'visibilityState');
      expect(api.board).toHaveBeenCalledTimes(1);
    });
  });

  describe('phone', () => {
    it('opens the move sheet on a long press and runs the chosen transition', async () => {
      phoneMedia(true);
      const api = fakeApi({
        board: jest.fn(withCards),
        guards: jest.fn(() => of(makeGuards())),
      });
      const { view } = await setup(api);
      expect(screen.getAllByRole('tab')).toHaveLength(5);
      view.container
        .querySelector('.bv__page .bv__item')!
        .dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
      await userEvent.click(await screen.findByRole('button', { name: 'Planung starten' }));
      expect(api.transition).toHaveBeenCalledWith('c-idea', 'T01', {}, 5);
    });

    it('opens the confirmation for another choice of the sheet', async () => {
      phoneMedia(true);
      const api = fakeApi({ board: jest.fn(withCards), guards: jest.fn(() => of(makeGuards())) });
      const { view } = await setup(api);
      const items = view.container.querySelectorAll('.bv__page .bv__item');
      items[1].dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
      await userEvent.click(await screen.findByRole('button', { name: 'Verwerfen' }));
      expect(await screen.findByRole('dialog', { name: 'Verwerfen' })).toBeInTheDocument();
    });
  });

  it('has no axe violations', async () => {
    const { view } = await setup();
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
