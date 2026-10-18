import { HttpErrorResponse } from '@angular/common/http';
import { Router, provideRouter } from '@angular/router';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../testing/a11y';
import { EventsApi } from '../dossiers/api/events-api.service';
import { fakeApi, makeEvent } from '../../../testing/event-fixtures';
import { TasksComponent } from './tasks.component';

const page = (items: ReturnType<typeof makeEvent>[]) => ({ items, total: items.length, limit: 200, offset: 0 });

describe('TasksComponent', () => {
  async function setup(api = fakeApi()) {
    const view = await render(TasksComponent, { providers: [provideRouter([]), { provide: EventsApi, useValue: api }] });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    return view;
  }

  it('lists dossiers that wait for the approval of the principal first', async () => {
    const waiting = makeEvent({ id: 'w', title: 'Wartet', state: 'in_review', allowedTransitions: ['T04'] });
    const own = makeEvent({ id: 'o', title: 'Eigenes', state: 'idea', allowedTransitions: ['T01'] });
    const done = makeEvent({ id: 'd', title: 'Vorbei', state: 'archived', allowedTransitions: [] });
    await setup(fakeApi({ list: jest.fn(() => of(page([waiting, own, done]))) }));
    expect(await screen.findByRole('heading', { name: 'Wartet auf deine Freigabe' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Wartet' })).toHaveAttribute('href', '/dossiers/w');
    expect(screen.getByRole('heading', { name: 'Meine Dossiers' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Eigenes' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Vorbei' })).not.toBeInTheDocument();
  });

  it('does not show the approval section without a task for it', async () => {
    await setup();
    expect(await screen.findByRole('link', { name: 'Movienight' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Wartet auf deine Freigabe' })).not.toBeInTheDocument();
  });

  it('shows the empty state with exactly one action', async () => {
    const view = await setup(fakeApi({ list: jest.fn(() => of(page([]))) }));
    expect(await screen.findByText('Gerade nichts zu tun.')).toBeInTheDocument();
    const navigate = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigateByUrl').mockResolvedValue(true);
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' })[1]);
    expect(navigate).toHaveBeenCalledWith('/dossiers/neu');
  });

  it('shows an error note when the load fails', async () => {
    await setup(fakeApi({ list: jest.fn(() => throwError(() => new HttpErrorResponse({ status: 500 }))) }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Aufgaben konnten nicht geladen werden.');
  });

  it('has no axe violations', async () => {
    const view = await setup();
    await screen.findByRole('link', { name: 'Movienight' });
    expect(await runAxe(view.container)).toHaveNoViolations();
  });

  it('names a dossier without organization', async () => {
    await setup(fakeApi({ list: jest.fn(() => of(page([makeEvent({ organization: null })]))) }));
    expect(await screen.findByText(/Ohne Organisation/)).toBeInTheDocument();
  });

  it('opens the new-event dialog route from the header button', async () => {
    const view = await setup();
    const navigate = jest.spyOn(view.fixture.debugElement.injector.get(Router), 'navigateByUrl').mockResolvedValue(true);
    await userEvent.click(screen.getAllByRole('button', { name: 'Neues Event' })[0]);
    expect(navigate).toHaveBeenCalledWith('/dossiers/neu');
  });
});
