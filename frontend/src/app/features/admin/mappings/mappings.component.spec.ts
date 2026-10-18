import { HttpErrorResponse } from '@angular/common/http';
import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { ToastService } from '@stupa-makers/ui-kit';
import { Subject, of, throwError } from 'rxjs';
import { runAxe } from '../../../../testing/a11y';
import { makeMapping, makePrincipal } from '../../../../testing/admin-fixtures';
import { FSI } from '../../../../testing/event-fixtures';
import { MappingsApi } from '../api/mappings-api.service';
import { SessionsApi } from '../api/sessions-api.service';
import { MappingsComponent } from './mappings.component';

function fakeMappings(overrides: Record<string, unknown> = {}) {
  return {
    list: jest.fn(() => of([makeMapping(), makeMapping({ id: 'map-2', oidcGroup: 'events-admin', role: 'admin', organization: null, principalCount: 1 })])),
    organizations: jest.fn(() => of([FSI])),
    create: jest.fn(() => of(makeMapping())),
    update: jest.fn(() => of(makeMapping())),
    remove: jest.fn(() => of(undefined)),
    createDefaults: jest.fn(() => of([makeMapping(), makeMapping({ id: 'map-3' }), makeMapping({ id: 'map-4' })])),
    principals: jest.fn(() => of({ items: [makePrincipal()], total: 1, limit: 200, offset: 0 })),
    ...overrides,
  };
}

async function setup(api = fakeMappings(), sessions = { revokePrincipal: jest.fn(() => of({ revoked: 2 })) }) {
  const view = await render(MappingsComponent, {
    providers: [
      { provide: MappingsApi, useValue: api },
      { provide: SessionsApi, useValue: sessions },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  const toast = view.fixture.debugElement.injector.get(ToastService);
  return { ...view, api, sessions, success: jest.spyOn(toast, 'success'), error: jest.spyOn(toast, 'error') };
}

describe('MappingsComponent', () => {
  it('lists group, role, organization and head count, with the Authentik note', async () => {
    await setup();
    expect(await screen.findByText('events-fsi-organizer')).toBeInTheDocument();
    expect(screen.getByText('Organisierend')).toBeInTheDocument();
    expect(screen.getByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText('Gruppen kommen aus Authentik. Mitglieder werden nur dort gepflegt.')).toBeInTheDocument();
  });

  it('shows the empty text when nothing is mapped', async () => {
    await setup(fakeMappings({ list: jest.fn(() => of([])) }));
    expect(await screen.findByText(/Noch keine Zuordnungen\./)).toBeInTheDocument();
  });

  it('demands an organization for an organization role before it posts', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Zuordnung hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Gruppe/ }), 'events-fsi-viewer');
    await userEvent.click(screen.getByRole('combobox', { name: /Rolle/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Lesend' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getByText('Org-Rolle braucht eine Organisation.')).toBeInTheDocument();
  });

  it('creates a global mapping without an organization and locks the organization select', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Zuordnung hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Gruppe/ }), ' events-editor ');
    await userEvent.click(screen.getByRole('combobox', { name: /Rolle/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Redaktion' }));
    expect(screen.getByRole('combobox', { name: 'Organisation' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.create).toHaveBeenCalledWith({ oidcGroup: 'events-editor', role: 'editor', organizationId: null });
  });

  it('shows the server code at the field, here the reserved prefix', async () => {
    const reserved = new HttpErrorResponse({ status: 422, error: { status: 422, code: 'reserved_group_prefix' } });
    await setup(fakeMappings({ create: jest.fn(() => throwError(() => reserved)) }));
    await userEvent.click(await screen.findByRole('button', { name: 'Zuordnung hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /Gruppe/ }), 'events-system:x');
    await userEvent.click(screen.getByRole('combobox', { name: /Rolle/ }));
    await userEvent.click(screen.getByRole('option', { name: 'Admin' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(await screen.findByText('Gruppe beginnt mit reserviertem Präfix events-system:.')).toBeInTheDocument();
  });

  it('keeps the group read-only on edit and patches role and organization', async () => {
    const { api } = await setup();
    const row = (await screen.findByText('events-fsi-organizer')).closest('tr') as HTMLElement;
    await userEvent.click(within(row).getByRole('button', { name: 'Bearbeiten' }));
    expect(screen.queryByRole('textbox', { name: /Gruppe/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.update).toHaveBeenCalledWith('map-1', { role: 'organizer', organizationId: 'org-fsi' });
  });

  it('edits a global mapping without an organization', async () => {
    const { api } = await setup();
    const row = (await screen.findByText('events-admin')).closest('tr') as HTMLElement;
    await userEvent.click(within(row).getByRole('button', { name: 'Bearbeiten' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.update).toHaveBeenCalledWith('map-2', expect.objectContaining({ role: 'admin' }));
  });

  it('demands a group and a role for a new mapping', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Zuordnung hinzufügen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.create).not.toHaveBeenCalled();
    expect(screen.getAllByText(/erforderlich|angeben|wählen/i).length).toBeGreaterThan(0);
  });

  it('toasts a failed default proposal', async () => {
    const down = new HttpErrorResponse({ status: 500, error: { status: 500, code: 'internal' } });
    const { error } = await setup(fakeMappings({ createDefaults: jest.fn(() => throwError(() => down)) }));
    await userEvent.click(await screen.findByRole('button', { name: /Standard/ }));
    expect(error).toHaveBeenCalled();
  });

  it('closes an open preview on a second click', async () => {
    const { api } = await setup();
    const row = (await screen.findByText('events-fsi-organizer')).closest('tr') as HTMLElement;
    const toggle = within(row).getByRole('button', { name: 'Wer bekommt was' });
    await userEvent.click(toggle);
    await userEvent.click(toggle);
    expect(screen.queryByText('Mia Muster')).not.toBeInTheDocument();
    expect(api.principals).toHaveBeenCalledTimes(1);
  });

  it('guards a second default run and a delete without a target', async () => {
    const pending = new Subject<never>();
    const { api, fixture } = await setup(fakeMappings({ createDefaults: jest.fn(() => pending) }));
    const page = fixture.componentInstance as unknown as { defaults(): void; confirmDelete(): void };
    page.defaults();
    page.defaults();
    page.confirmDelete();
    expect(api.createDefaults).toHaveBeenCalledTimes(1);
    expect(api.remove).not.toHaveBeenCalled();
  });

  it('deletes only after the confirmation dialog', async () => {
    const { api } = await setup();
    const row = (await screen.findByText('events-fsi-organizer')).closest('tr') as HTMLElement;
    await userEvent.click(within(row).getByRole('button', { name: 'Löschen' }));
    const dialog = await screen.findByRole('dialog');
    expect(api.remove).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Löschen' }));
    expect(api.remove).toHaveBeenCalledWith('map-1');
  });

  it('tells the last-admin rule as a toast when the delete is refused', async () => {
    const refused = new HttpErrorResponse({ status: 409, error: { status: 409, code: 'last_admin_mapping' } });
    const { error } = await setup(fakeMappings({ remove: jest.fn(() => throwError(() => refused)) }));
    const row = (await screen.findByText('events-admin')).closest('tr') as HTMLElement;
    await userEvent.click(within(row).getByRole('button', { name: 'Löschen' }));
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Löschen' }));
    expect(error).toHaveBeenCalledWith('Die letzte Admin-Zuordnung bleibt, solange keine Bootstrap-Admins gesetzt sind.');
  });

  it('creates the default mappings and reports how many are new', async () => {
    const { api, success } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Standardzuordnungen anlegen' }));
    expect(api.createDefaults).toHaveBeenCalled();
    expect(success).toHaveBeenCalledWith('3 neue Zuordnungen angelegt');
  });

  it('previews the people of a group and revokes their sessions after a confirmation', async () => {
    const { api, sessions, success } = await setup();
    const row = (await screen.findByText('events-fsi-organizer')).closest('tr') as HTMLElement;
    await userEvent.click(within(row).getByRole('button', { name: 'Wer bekommt was' }));
    expect(await screen.findByText('Mia Muster')).toBeInTheDocument();
    expect(api.principals).toHaveBeenCalledWith('events-fsi-organizer');
    expect(screen.getByText('mia@example.test')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Sitzungen widerrufen' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Diese Person muss sich neu anmelden. Rechte ändern sich nur über Authentik.');
    expect(sessions.revokePrincipal).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sitzungen widerrufen' }));
    expect(sessions.revokePrincipal).toHaveBeenCalledWith('p-1');
    expect(success).toHaveBeenCalledWith('2 Sitzungen beendet.');
  });

  it('has no axe violations', async () => {
    const view = await setup();
    await screen.findByText('events-admin');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
