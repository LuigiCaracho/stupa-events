/** Spec for the venue pin sheet: the search rules, the three failure texts, the source of an applied pin. */
import { HttpErrorResponse } from '@angular/common/http';
import { MapLoaderService } from '@shared/ui/map/map-loader.service';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { of, throwError } from 'rxjs';
import { makeVenue } from '../../../../../testing/admin-fixtures';
import type { VenueGeocode } from '../../api/admin.models';
import { TaxonomyApi } from '../../api/taxonomy-api.service';
import { searchBlock } from './venue-geocode';
import { VenuePinSheetComponent } from './venue-pin-sheet.component';

const ADDRESS = { address: 'Alteburgstraße 150', city: 'Reutlingen' };
const FOUND: VenueGeocode = {
  found: true,
  lat: '48.482617',
  lon: '9.187312',
  displayName: 'x',
  cached: false,
  attribution: '© OpenStreetMap',
};

const problem = (status: number, code?: string) =>
  throwError(() => new HttpErrorResponse({ status, error: { status, code } }));

async function setup(venue = makeVenue(ADDRESS), geocode: jest.Mock = jest.fn(() => of(FOUND))) {
  const applied = jest.fn();
  await render(VenuePinSheetComponent, {
    inputs: { open: true, venue },
    on: { applied },
    providers: [
      { provide: TaxonomyApi, useValue: { geocodeVenue: geocode } },
      { provide: MapLoaderService, useValue: { load: () => new Promise(() => undefined) } },
    ],
  });
  return { applied, geocode };
}

describe('searchBlock', () => {
  it('allows only a saved, public venue with address and city', () => {
    expect(searchBlock(makeVenue(ADDRESS))).toBeNull();
    expect(searchBlock(makeVenue({ ...ADDRESS, isPrivate: true }))).toBe('admin.pin.private');
    expect(searchBlock(makeVenue({ address: 'x', city: null }))).toBe('admin.pin.noAddress');
    expect(searchBlock(makeVenue({ ...ADDRESS, id: 'new' }))).toBe('admin.pin.saveFirst');
    expect(searchBlock(null)).toBe('admin.pin.saveFirst');
  });
});

describe('VenuePinSheetComponent', () => {
  it('disables the search for a private venue and never calls the server', async () => {
    const { geocode } = await setup(makeVenue({ ...ADDRESS, isPrivate: true }));
    const button = screen.getByRole('button', { name: 'Adresse suchen' });
    expect(button).toBeDisabled();
    expect(screen.getByText('Private Orte werden nicht extern gesucht.')).toBeInTheDocument();
    await userEvent.click(button);
    expect(geocode).not.toHaveBeenCalled();
  });

  it('disables the search without address and city', async () => {
    await setup(makeVenue());
    expect(screen.getByRole('button', { name: 'Adresse suchen' })).toBeDisabled();
    expect(screen.getByText('Zum Suchen fehlen Adresse und Ort.')).toBeInTheDocument();
  });

  it('proposes the found position with the OSM note and applies it as a search result', async () => {
    const { applied } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Adresse suchen' }));
    expect(
      await screen.findByText(/Vorschlag von OpenStreetMap\. Prüfe den Pin\./),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    expect(applied).toHaveBeenCalledWith({ lat: 48.482617, lon: 9.187312, source: 'nominatim' });
  });

  it('keeps apply off until there is a pin', async () => {
    await setup();
    expect(screen.getByRole('button', { name: 'Übernehmen' })).toBeDisabled();
  });

  it.each([
    [404, undefined, 'Die Adresssuche ist fehlgeschlagen.'],
    [429, 'geocode_rate', 'Bitte warte kurz, die Suche läuft höchstens alle 2 Sekunden.'],
    [503, 'geocode_disabled', 'Die Adresssuche ist nicht eingerichtet.'],
  ])('explains a %s answer', async (status, code, text) => {
    await setup(
      makeVenue(ADDRESS),
      jest.fn(() => problem(status, code)),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Adresse suchen' }));
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it('says so when the address is not found', async () => {
    await setup(
      makeVenue(ADDRESS),
      jest.fn(() => of({ ...FOUND, found: false, lat: null, lon: null })),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Adresse suchen' }));
    expect(
      await screen.findByText('Adresse nicht gefunden. Setz den Pin von Hand.'),
    ).toBeInTheDocument();
  });
});
