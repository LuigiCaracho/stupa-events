import { HttpErrorResponse } from '@angular/common/http';
import { Router, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../testing/a11y';
import { fakeApi, makeCard, makeTasks } from '../../../testing/event-fixtures';
import { EventsApi } from '../dossiers/api/events-api.service';
import type { TasksOut } from '../dossiers/api/task.models';
import { TasksComponent } from './tasks.component';

const waiting = {
  ...makeCard({ id: 'w', title: 'Wartet', state: 'in_review', startsAt: '2099-11-05T18:00:00Z' }),
  fourEyesBlocked: false,
};
const own = makeCard({ id: 'o', title: 'Eigenes', state: 'planning' });
const idea = makeCard({ id: 'i', title: 'Idee', state: 'idea' });
const changed = {
  ...makeCard({ id: 'c', title: 'Geändert', state: 'live' }),
  baselineRev: 4,
  changes: [],
};

const withTasks = (overrides: Partial<TasksOut>) =>
  fakeApi({ tasks: jest.fn(() => of(makeTasks(overrides))) });

describe('TasksComponent', () => {
  async function setup(api = fakeApi()) {
    const view = await render(TasksComponent, {
      providers: [provideRouter([]), { provide: EventsApi, useValue: api }],
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    const navigate = jest.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    return {
      view,
      api,
      navigate,
      toasts: () =>
        TestBed.inject(ToastService)
          .toasts()
          .map((t) => t.message),
    };
  }

  it('shows the empty state with one action when there is nothing to do', async () => {
    const { navigate } = await setup();
    expect(await screen.findByText('Gerade nichts zu tun.')).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' })[1]);
    expect(navigate).toHaveBeenCalledWith('/dossiers/neu');
  });

  it('shows one h2 per section with its count, starting with the approval', async () => {
    const api = withTasks({
      awaitingReview: [waiting],
      mine: [own, idea],
      counts: {
        awaitingReview: 1,
        returned: 0,
        due: 0,
        mine: 2,
        followupOpen: 0,
        changedAfterPublish: 0,
      },
    });
    await setup(api);
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent?.trim());
    expect(headings).toEqual(['Wartet auf deine Freigabe', 'Meine Dossiers']);
    expect(screen.getByRole('link', { name: 'Wartet' })).toHaveAttribute('href', '/dossiers/w');
    expect(screen.getByText(/in \d+ Tagen/)).toBeInTheDocument();
  });

  it('lists the own dossiers by state, earliest phase first', async () => {
    const api = withTasks({
      mine: [own, idea],
      counts: {
        awaitingReview: 0,
        returned: 0,
        due: 0,
        mine: 2,
        followupOpen: 0,
        changedAfterPublish: 0,
      },
    });
    await setup(api);
    const links = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(links).toEqual(['Idee', 'Eigenes']);
  });

  it('says that another person has to approve', async () => {
    const api = withTasks({
      awaitingReview: [{ ...waiting, fourEyesBlocked: true }],
      counts: {
        awaitingReview: 1,
        returned: 0,
        due: 0,
        mine: 0,
        followupOpen: 0,
        changedAfterPublish: 0,
      },
    });
    await setup(api);
    expect(screen.getByText('Eine andere Person muss freigeben.')).toBeInTheDocument();
  });

  it('shows the question of a return with the person and the day', async () => {
    const returned = {
      ...makeCard({ id: 'r', title: 'Zurück' }),
      note: 'Bitte Ort klären',
      returnedAt: '2026-10-17T10:00:00Z',
      returnedBy: { sub: 'p', displayName: 'Anna' },
    };
    await setup(
      withTasks({ returned: [returned], counts: { ...makeTasks().counts, returned: 1 } }),
    );
    expect(screen.getByRole('heading', { name: 'Rückfragen an dich' })).toBeInTheDocument();
    expect(screen.getByText(/Anna, .*: Bitte Ort klären/)).toBeInTheDocument();
  });

  it('shows the sections "Fällig" and "Nachbereitung offen" only with entries', async () => {
    await setup(
      withTasks({
        due: [own],
        followupOpen: [idea],
        counts: { ...makeTasks().counts, due: 1, followupOpen: 1 },
      }),
    );
    expect(screen.getByRole('heading', { name: 'Fällig' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Nachbereitung offen' })).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Nachträglich geändert' }),
    ).not.toBeInTheDocument();
  });

  describe('changed after publishing', () => {
    const api = () =>
      withTasks({
        changedAfterPublish: [changed],
        counts: { ...makeTasks().counts, changedAfterPublish: 1 },
      });

    it('acknowledges a change', async () => {
      const fake = api();
      const { toasts } = await setup(fake);
      await userEvent.click(screen.getByRole('button', { name: 'Gesehen' }));
      expect(fake.action).toHaveBeenCalledWith('c', 'acknowledge-changes', {}, 3);
      expect(toasts()).toContain('Als gesehen markiert.');
      expect(fake.tasks).toHaveBeenCalledTimes(2);
    });

    it('resets to the published revision after asking for an optional note', async () => {
      const fake = api();
      await setup(fake);
      await userEvent.click(screen.getByRole('button', { name: 'Zurücksetzen' }));
      const dialog = await screen.findByRole('dialog', {
        name: 'Auf den veröffentlichten Stand zurücksetzen',
      });
      await userEvent.type(within(dialog).getByLabelText('Notiz (optional)'), 'Tippfehler');
      await userEvent.click(within(dialog).getByRole('button', { name: 'Zurücksetzen' }));
      expect(fake.action).toHaveBeenCalledWith(
        'c',
        'revert-revision',
        { rev: 4, note: 'Tippfehler' },
        3,
      );
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('names the reason when the reset is refused', async () => {
      const fake = api();
      fake.action.mockReturnValue(
        throwError(
          () =>
            new HttpErrorResponse({
              status: 409,
              error: { status: 409, code: 'revert_poster_replaced' },
            }),
        ),
      );
      const { toasts } = await setup(fake);
      await userEvent.click(screen.getByRole('button', { name: 'Gesehen' }));
      expect(toasts()[0]).toContain('Poster der alten Fassung');
    });
  });

  it('shows an error note when the load fails', async () => {
    await setup(
      fakeApi({ tasks: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Die Aufgaben konnten nicht geladen werden.',
    );
  });

  it('has no axe violations', async () => {
    const api = withTasks({
      awaitingReview: [waiting],
      mine: [own],
      changedAfterPublish: [changed],
      counts: {
        awaitingReview: 1,
        returned: 0,
        due: 0,
        mine: 1,
        followupOpen: 0,
        changedAfterPublish: 1,
      },
    });
    const { view } = await setup(api);
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('opens the new-event route from the header button', async () => {
    const { navigate } = await setup();
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' })[0]);
    expect(navigate).toHaveBeenCalledWith('/dossiers/neu');
  });
});
