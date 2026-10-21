import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { runAxe } from '../../../../../testing/a11y';
import { makeCategory, makeOrganization } from '../../../../../testing/admin-fixtures';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { OrganizationsComponent } from './organizations.component';

function fakeTaxonomy() {
  return {
    organizations: jest.fn(() =>
      of([
        makeOrganization(),
        makeOrganization({
          id: 'org-mk',
          slug: 'makers',
          name: 'MAKERS',
          short: 'MK',
          kind: 'partner',
          instagram: [],
        }),
      ]),
    ),
    categories: jest.fn(() => of([makeCategory({ id: 'c1', name: 'Informatik' })])),
    createOrganization: jest.fn(() => of(makeOrganization())),
    updateOrganization: jest.fn(() => of(makeOrganization())),
  };
}

async function setup() {
  const api = fakeTaxonomy();
  const view = await render(OrganizationsComponent, {
    providers: [{ provide: TaxonomyApi, useValue: api }],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, api };
}

describe('OrganizationsComponent', () => {
  it('still lists organizations when the category lookup fails', async () => {
    const api = {
      ...fakeTaxonomy(),
      categories: jest.fn(() => throwError(() => new Error('down'))),
    };
    await render(OrganizationsComponent, { providers: [{ provide: TaxonomyApi, useValue: api }] });
    expect(await screen.findByText('Fachschaft Informatik')).toBeInTheDocument();
  });

  it('lists name, kind, short and instagram', async () => {
    await setup();
    expect(await screen.findByText('Fachschaft Informatik')).toBeInTheDocument();
    expect(screen.getByText('fsi_rt')).toBeInTheDocument();
    expect(screen.getByText('Partner')).toBeInTheDocument();
  });

  it('has no trust switch and saves the row without one', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Fachschaft Informatik'));
    expect(screen.queryByRole('switch', { name: 'Vertraut' })).not.toBeInTheDocument();
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

  it('splits the instagram accounts at commas on create', async () => {
    const { api } = await setup();
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
    const view = await setup();
    await screen.findByText('MAKERS');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
