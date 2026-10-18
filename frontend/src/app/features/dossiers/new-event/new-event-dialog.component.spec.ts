import { HttpErrorResponse } from '@angular/common/http';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../testing/a11y';
import { EventsApi } from '../api/events-api.service';
import { FSI, fakeApi, fakeAuth, makeEvent } from '../../../../testing/event-fixtures';
import { NewEventDialogComponent } from './new-event-dialog.component';

const MAKERS = { id: 'org-makers', slug: 'makers', name: 'MAKERS', short: 'MKR' };

describe('NewEventDialogComponent', () => {
  async function setup(api = fakeApi(), auth = fakeAuth()) {
    const created = jest.fn();
    const closed = jest.fn();
    const view = await render(NewEventDialogComponent, {
      providers: [
        { provide: EventsApi, useValue: api },
        { provide: AuthService, useValue: auth },
      ],
      on: { created, closed },
    });
    await view.fixture.whenStable();
    view.fixture.detectChanges();
    return { view, api, created, closed };
  }

  async function fillRequired() {
    await userEvent.type(screen.getByLabelText(/Titel/), '  Movienight ');
    await userEvent.type(screen.getByLabelText(/Beginn, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Beginn, Uhrzeit/), '19:30');
    await userEvent.tab();
  }

  it('validates title, start and organization before it posts', async () => {
    const { api } = await setup(
      fakeApi({ organizations: jest.fn(() => of([FSI, MAKERS])) }),
      fakeAuth({ organizations: () => [{ slug: 'fsi', role: 'organizer' }, { slug: 'makers', role: 'organizer' }] }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getByText('Titel fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Organisation fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Beginn fehlt.')).toBeInTheDocument();
  });

  it('preselects the only own organization and posts UTC instants with a default end', async () => {
    const { api, created } = await setup();
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).toHaveBeenCalledWith({
      title: 'Movienight',
      startsAt: '2026-11-05T18:30:00Z',
      endsAt: '2026-11-05T20:30:00Z',
      tzid: 'Europe/Berlin',
      allDay: false,
      organizationId: 'org-fsi',
    });
    expect(created).toHaveBeenCalledWith(makeEvent({ state: 'idea' }));
  });

  it('offers only the own organizations unless the principal reads all', async () => {
    const api = fakeApi({ organizations: jest.fn(() => of([FSI, MAKERS])) });
    await setup(api, fakeAuth({ organizations: () => [{ slug: 'makers', role: 'organizer' }] }));
    await userEvent.click(screen.getByRole('combobox', { name: /Organisation/ }));
    expect(screen.getAllByRole('option').map((o) => o.textContent?.trim())).toEqual(['MAKERS']);
  });

  it('offers the category tree with children indented under their parent', async () => {
    const tree = [
      { id: 'fs', slug: 'fs', name: 'Fachschaften', kind: 'fachschaft', children: [{ id: 'fsi', slug: 'fsi', name: 'Informatik', kind: 'fachschaft' }] },
      { id: 'kino', slug: 'kino', name: 'Kino', kind: 'format' },
    ];
    await setup(fakeApi({ categories: jest.fn(() => of(tree)) }));
    await userEvent.click(screen.getByRole('combobox', { name: /Format oder Kategorie/ }));
    expect(screen.getAllByRole('option').map((o) => o.textContent?.trim())).toEqual(['Optional', 'Fachschaften', 'Informatik', 'Kino']);
  });

  it('refuses an end before the start', async () => {
    const { api } = await setup();
    await fillRequired();
    await userEvent.type(screen.getByLabelText(/Ende, Datum/), '05.11.2026');
    await userEvent.tab();
    await userEvent.type(screen.getByLabelText(/Ende, Uhrzeit/), '18:00');
    await userEvent.tab();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getByText('Ende liegt vor dem Beginn.')).toBeInTheDocument();
  });

  it('keeps the dialog open and does not emit when the server refuses', async () => {
    const forbidden = new HttpErrorResponse({ status: 404, error: { status: 404, code: 'not_found' } });
    const { created } = await setup(fakeApi({ create: jest.fn(() => throwError(() => forbidden)) }));
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(created).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('says so when the principal has no organization', async () => {
    await setup(fakeApi({ organizations: jest.fn(() => of([])) }));
    expect(screen.getByRole('alert')).toHaveTextContent('keine Organisation freigeschaltet');
  });

  it('closes from the cancel button and has no axe violations', async () => {
    const { closed } = await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });
});
