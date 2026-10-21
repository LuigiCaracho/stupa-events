import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { render, screen } from '@testing-library/angular';
import { ToastService } from '@stupa-makers/ui-kit';
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
    return {
      view,
      api,
      created,
      closed,
      toasts: () =>
        TestBed.inject(ToastService)
          .toasts()
          .map((t) => t.message),
    };
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
      fakeAuth({
        organizations: () => [
          { slug: 'fsi', role: 'organizer' },
          { slug: 'makers', role: 'organizer' },
        ],
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getByText('Titel fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Organisation fehlt.')).toBeInTheDocument();
    expect(screen.getByText('Beginn fehlt.')).toBeInTheDocument();
  });

  it('preselects the only own organization and posts UTC instants without an end', async () => {
    const { api, created } = await setup();
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).toHaveBeenCalledWith({
      title: 'Movienight',
      startsAt: '2026-11-05T18:30:00Z',
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
      {
        id: 'fs',
        slug: 'fs',
        name: 'Fachschaften',
        kind: 'fachschaft',
        children: [{ id: 'fsi', slug: 'fsi', name: 'Informatik', kind: 'fachschaft' }],
      },
      { id: 'kino', slug: 'kino', name: 'Kino', kind: 'format' },
    ];
    await setup(fakeApi({ categories: jest.fn(() => of(tree)) }));
    await userEvent.click(screen.getByRole('combobox', { name: /Format oder Kategorie/ }));
    expect(screen.getAllByRole('option').map((o) => o.textContent?.trim())).toEqual([
      'Optional',
      'Fachschaften',
      'Informatik',
      'Kino',
    ]);
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

  it('names the organization scope when the server answers 404', async () => {
    const hidden = new HttpErrorResponse({
      status: 404,
      error: { status: 404, code: 'not_found' },
    });
    const { created, toasts } = await setup(
      fakeApi({ create: jest.fn(() => throwError(() => hidden)) }),
    );
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(created).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(toasts()).toEqual(['Für diese Organisation darfst du keine Events anlegen.']);
  });

  it('shows a proposal without organization when the principal has none', async () => {
    const { api, created } = await setup(
      fakeApi({ organizations: jest.fn(() => of([])) }),
      fakeAuth({ organizations: () => [] }),
    );
    expect(screen.getByRole('dialog', { name: 'Event vorschlagen' })).toBeInTheDocument();
    const field = screen.getByLabelText('Organisation');
    expect(field).toBeDisabled();
    expect(field).toHaveValue('Vorschlag, ohne Organisation');
    expect(
      screen.getByText('Du kannst bis zu 5 Vorschläge gleichzeitig offen haben.'),
    ).toBeInTheDocument();
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(api.create).toHaveBeenCalledWith(
      expect.not.objectContaining({ organizationId: expect.anything() }),
    );
    expect(created).toHaveBeenCalled();
  });

  it('tells about the quota of five open proposals', async () => {
    const quota = new HttpErrorResponse({
      status: 422,
      error: { status: 422, code: 'proposal_quota_exceeded' },
    });
    const { toasts } = await setup(
      fakeApi({
        organizations: jest.fn(() => of([])),
        create: jest.fn(() => throwError(() => quota)),
      }),
      fakeAuth({ organizations: () => [] }),
    );
    await fillRequired();
    await userEvent.click(screen.getByRole('button', { name: 'Anlegen' }));
    expect(toasts()[0]).toContain('Du hast schon 5 offene Vorschläge.');
  });

  it('closes from the cancel button and has no axe violations', async () => {
    const { closed } = await setup();
    expect(await runAxe(document.body)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(closed).toHaveBeenCalled();
  });

  it('offers the second tab "Aus Vorlage" and asks the page to switch', async () => {
    const switchToTemplate = jest.fn();
    await render(NewEventDialogComponent, {
      providers: [
        { provide: EventsApi, useValue: fakeApi() },
        { provide: AuthService, useValue: fakeAuth() },
      ],
      on: { switchToTemplate },
    });
    expect(screen.getByRole('radio', { name: 'Neu' })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: 'Aus Vorlage' }));
    expect(switchToTemplate).toHaveBeenCalled();
  });
});
