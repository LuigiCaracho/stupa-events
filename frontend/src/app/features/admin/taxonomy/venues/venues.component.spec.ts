import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of } from 'rxjs';
import { runAxe } from '../../../../../testing/a11y';
import { makeVenue } from '../../../../../testing/admin-fixtures';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { VenuesComponent } from './venues.component';

function fakeTaxonomy() {
  return {
    venues: jest.fn(() =>
      of([
        makeVenue(),
        makeVenue({ id: 'ven-3', slug: 'foyer', name: 'Foyer', buildingNo: null, roomKey: null }),
        makeVenue({
          id: 'ven-4',
          slug: 'hoersaal',
          name: 'Hörsaal',
          lat: 48.4829,
          lon: 9.1873,
          geocodeSource: 'nominatim',
        }),
        makeVenue({
          id: 'ven-2',
          slug: 'aula',
          name: 'Aula',
          address: 'Alteburgstraße 150',
          postcode: '72762',
          city: 'Reutlingen',
        }),
      ]),
    ),
    createVenue: jest.fn(() => of(makeVenue())),
    updateVenue: jest.fn(() => of(makeVenue())),
  };
}

async function setup() {
  const api = fakeTaxonomy();
  const view = await render(VenuesComponent, {
    providers: [{ provide: TaxonomyApi, useValue: api }],
  });
  await view.fixture.whenStable();
  view.fixture.detectChanges();
  return { ...view, api };
}

describe('VenuesComponent', () => {
  it('lists venues with and without an address and shows a pin or "Noch kein Pin gesetzt."', async () => {
    await setup();
    expect(await screen.findByText('Alteburgstraße 150')).toBeInTheDocument();
    expect(screen.getByText('Kinosaal')).toBeInTheDocument();
    expect(screen.getByText('48.4829, 9.1873')).toBeInTheDocument();
    expect(screen.getByText('per Adresssuche')).toBeInTheDocument();
    expect(screen.getAllByText('Noch kein Pin gesetzt.').length).toBe(3);
    expect(screen.queryAllByRole('spinbutton')).toHaveLength(0);
  });

  it('edits the coordinates as a pair and sends them as numbers', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Foyer'));
    await userEvent.type(screen.getByRole('spinbutton', { name: 'Breite' }), '48.4829');
    await userEvent.type(screen.getByRole('spinbutton', { name: 'Länge' }), '9.1873');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateVenue).toHaveBeenCalledWith(
      'ven-3',
      expect.objectContaining({ lat: 48.4829, lon: 9.1873 }),
    );
    expect((api.updateVenue as jest.Mock).mock.calls[0][1]).not.toHaveProperty('geocodeSource');
  });

  it('refuses one coordinate without the other', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Foyer'));
    await userEvent.type(screen.getByRole('spinbutton', { name: 'Breite' }), '48.4');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateVenue).not.toHaveBeenCalled();
    expect(await screen.findByText('Breite und Länge nur zusammen.')).toBeInTheDocument();
  });

  it('does not resend an unchanged pin, which would reset its source', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Hörsaal'));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect((api.updateVenue as jest.Mock).mock.calls[0][1]).not.toHaveProperty('lat');
  });

  it('opens the pin sheet from the edit row', async () => {
    await setup();
    await userEvent.click(await screen.findByText('Foyer'));
    await userEvent.click(screen.getByRole('button', { name: 'Pin setzen' }));
    expect(await screen.findByRole('dialog', { name: 'Pin setzen' })).toBeInTheDocument();
  });

  it('creates a venue without an address and turns blank texts into null', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByRole('button', { name: 'Hinzufügen' }));
    await userEvent.type(screen.getByRole('textbox', { name: /^Name/ }), 'Foyer');
    await userEvent.type(screen.getByRole('textbox', { name: /Slug/ }), 'foyer');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.createVenue).toHaveBeenCalledWith({
      slug: 'foyer',
      name: 'Foyer',
      address: null,
      postcode: null,
      city: null,
      buildingNo: null,
      roomKey: null,
      publicPrecision: 'building',
      isPrivate: false,
      active: true,
    });
  });

  it('edits an existing venue and sends no slug', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Aula'));
    const city = screen.getByRole('textbox', { name: 'Stadt' });
    await userEvent.clear(city);
    await userEvent.type(city, 'Tübingen');
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateVenue).toHaveBeenCalledWith(
      'ven-2',
      expect.objectContaining({ city: 'Tübingen', address: 'Alteburgstraße 150' }),
    );
    expect((api.updateVenue as jest.Mock).mock.calls[0][1]).not.toHaveProperty('slug');
  });

  it('edits a venue without an address and keeps its blank texts null', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Kinosaal'));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateVenue).toHaveBeenCalledWith(
      'ven-1',
      expect.objectContaining({
        address: null,
        postcode: null,
        city: null,
        buildingNo: '9',
        roomKey: '133',
      }),
    );
  });

  it('keeps a missing building and room key null', async () => {
    const { api } = await setup();
    await userEvent.click(await screen.findByText('Foyer'));
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(api.updateVenue).toHaveBeenCalledWith(
      'ven-3',
      expect.objectContaining({ buildingNo: null, roomKey: null }),
    );
  });

  it('has no axe violations', async () => {
    const view = await setup();
    await screen.findByText('Aula');
    expect(await runAxe(view.container)).toHaveNoViolations();
  });
});
