import { render, screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { AuthService } from '@core/auth/auth.service';
import { runAxe } from '../../../../../testing/a11y';
import { makeCategory, makeOrganization } from '../../../../../testing/admin-fixtures';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { OrganizationsComponent } from './organizations.component';

function fakeTaxonomy() {
  return {
    organizations: jest.fn(() => of([makeOrganization(), makeOrganization({ id: 'org-mk', slug: 'makers', name: 'MAKERS', short: 'MK', kind: 'partner', trusted: true, instagram: [] })])),
    categories: jest.fn(() => of([makeCategory({ id: 'c1', name: 'Informatik' })])),
    createOrganization: jest.fn(() => of(makeOrganization())),
    updateOrganization: jest.fn(() => of(makeOrganization())),
  };
}

async function setup(canTrust: boolean) {
  const api = fakeTaxonomy();
  const view = await render(OrganizationsComponent, {
    providers: [
      { provide: TaxonomyApi, useValue: api },
      { provide: AuthService, useValue: { can: (p: string) => canTrust && p === 'admin.mappings' } },
    ],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, api };
}

describe('OrganizationsComponent', () => {
  it('still lists organizations when the category lookup fails', async () => {
    const api = { ...fakeTaxonomy(), categories: jest.fn(() => throwError(() => new Error('down'))) };
    await render(OrganizationsComponent, {
      providers: [
        { provide: TaxonomyApi, useValue: api },
        { provide: AuthService, useValue: { can: () => false } },
      ],
    });
    expect(await screen.findByText('Fachschaft Informatik')).toBeInTheDocument();
  });

  it('lists name, kind, short, instagram and the trusted flag', async () => {
    await setup(false);
    expect(await screen.findByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText('fsi_rt')).toBeInTheDocument();
    expect(screen.getByText('Partner')).toBeInTheDocument();
  });

  it('disables the trusted switch with a reason and leaves trusted out of the body without admin.mappings', async () => {
    const { api } = await setup(false);
    await userEvent.click(await screen.findByText('Fachschaft Informatik'));
    expect(screen.getByRole('switch', { name: 'Vertraut' })).toBeDisabled();
    expect(screen.getByText('Nur mit Admin-Recht änderbar.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateOrganization).toHaveBeenCalledWith('org-fsi', {
      name: 'Fachschaft Informatik',
      kind: 'fachschaft',
      short: 'FSI',
      categoryId: null,
      instagram: ['fsi_rt'],
      active: true,
    });
  });

  it('asks before it trusts an organization and sends trusted after the confirmation', async () => {
    const { api } = await setup(true);
    await userEvent.click(await screen.findByText('Fachschaft Informatik'));
    await userEvent.click(screen.getByRole('switch', { name: 'Vertraut' }));
    expect(await screen.findByRole('dialog')).toHaveTextContent('Approver dieser Organisation dürfen eigene Events veröffentlichen.');
    await userEvent.click(screen.getByRole('button', { name: 'Vertrauen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateOrganization).toHaveBeenCalledWith('org-fsi', expect.objectContaining({ trusted: true }));
  });

  it('keeps trusted off when the confirmation is cancelled', async () => {
    const { api } = await setup(true);
    await userEvent.click(await screen.findByText('Fachschaft Informatik'));
    await userEvent.click(screen.getByRole('switch', { name: 'Vertraut' }));
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Abbrechen' }));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateOrganization).toHaveBeenCalledWith('org-fsi', expect.objectContaining({ trusted: false }));
  });

  it('splits the instagram accounts at commas on create', async () => {
    const { api } = await setup(false);
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /^Name/ }), 'Neue Org');
    await userEvent.type(screen.getByRole('textbox', { name: /Slug/ }), 'neue-org');
    await userEvent.type(screen.getByRole('textbox', { name: 'Instagram' }), 'a_b, c_d ,');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.createOrganization).toHaveBeenCalledWith(
      expect.objectContaining({ slug: 'neue-org', instagram: ['a_b', 'c_d'] }),
    );
  });

  it('has no axe violations', async () => {
    const view = await setup(true);
    await screen.findByText('MAKERS');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
