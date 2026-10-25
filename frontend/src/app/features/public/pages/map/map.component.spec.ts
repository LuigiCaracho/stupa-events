/** Spec for P11 Weltkarte: the request per filter state, the list twin of the map, "In meiner Nähe" without a request. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MapLoaderService } from '@shared/ui/map/map-loader.service';
import { GEOLOCATION } from '@shared/ui/map/near-me.service';
import { screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { CATEGORIES } from '../../../../../testing/public-fixtures';
import type { PublicMapCollection, PublicMapFeature } from '../../model/map.models';
import { MapPageComponent } from './map.component';

const feature = (
  slug: string,
  title: string,
  lon: number,
  lat: number,
  startsAt: string,
): PublicMapFeature => ({
  type: 'Feature',
  geometry: { type: 'Point', coordinates: [lon, lat] },
  properties: {
    slug,
    title,
    startsAt,
    endsAt: startsAt,
    status: 'scheduled',
    categorySlug: null,
    imageThumb: null,
    venueName: 'Ort ' + slug,
    precision: 'exact',
  },
});

const body = (features: PublicMapFeature[], truncated = false): PublicMapCollection => ({
  type: 'FeatureCollection',
  generatedAt: '2026-10-25T10:00:00Z',
  truncated,
  features,
});

const FAR = feature('davos', 'Skiausfahrt Davos', 9.84, 46.8, '2026-11-01T08:00:00Z');
const NEAR = feature('campus', 'Kinoabend', 9.19, 48.48, '2026-11-05T18:00:00Z');

async function setup(url: string, geolocation: Geolocation | null = null) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: 'karte', component: MapPageComponent }]),
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: MapLoaderService, useValue: { load: () => new Promise(() => undefined) } },
      { provide: GEOLOCATION, useValue: geolocation },
    ],
  });
  const harness = await RouterTestingHarness.create();
  await harness.navigateByUrl(url, MapPageComponent);
  harness.detectChanges();
  return { harness, http: TestBed.inject(HttpTestingController), router: TestBed.inject(Router) };
}

type Ctx = Awaited<ReturnType<typeof setup>>;

async function respond(ctx: Ctx, data: PublicMapCollection) {
  ctx.http.expectOne((r) => r.url === '/api/public/map/events').flush(data);
  ctx.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
  await ctx.harness.fixture.whenStable();
  ctx.harness.detectChanges();
}

describe('MapPageComponent', () => {
  it('asks for upcoming events without a bbox and lists them by date', async () => {
    const ctx = await setup('/karte');
    const req = ctx.http.expectOne((r) => r.url === '/api/public/map/events');
    expect(req.request.params.keys()).toEqual([]);
    req.flush(body([NEAR, FAR]));
    ctx.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
    await ctx.harness.fixture.whenStable();
    ctx.harness.detectChanges();
    const links = screen
      .getAllByRole('link')
      .filter((a) => a.getAttribute('href')?.startsWith('/e/'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/e/davos', '/e/campus']);
  });

  it('maps the URL to past, year and categories', async () => {
    const ctx = await setup('/karte?vergangen=1&jahr=2025&k=kino&k=party');
    const req = ctx.http.expectOne((r) => r.url === '/api/public/map/events');
    expect(req.request.params.get('past')).toBe('1');
    expect(req.request.params.get('from')).toBe('2025-01-01');
    expect(req.request.params.get('to')).toBe('2025-12-31');
    expect(req.request.params.getAll('category')).toEqual(['kino', 'party']);
    req.flush(body([]));
    ctx.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
  });

  it('switches the time filter through the URL', async () => {
    const ctx = await setup('/karte');
    await respond(ctx, body([FAR]));
    await userEvent.click(screen.getByRole('radio', { name: /Gab es/ }));
    await ctx.harness.fixture.whenStable();
    expect(ctx.router.url).toBe('/karte?vergangen=1');
    ctx.http.match((r) => r.url === '/api/public/map/events').forEach((r) => r.flush(body([])));
  });

  it('sorts by distance in the browser and sends no request with the position', async () => {
    const geo = {
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { latitude: 48.4829, longitude: 9.1873 } } as GeolocationPosition),
    } as Geolocation;
    const ctx = await setup('/karte', geo);
    await respond(ctx, body([FAR, NEAR]));
    await userEvent.click(screen.getByRole('button', { name: 'In meiner Nähe' }));
    ctx.harness.detectChanges();
    const hrefs = screen
      .getAllByRole('link')
      .map((a) => a.getAttribute('href'))
      .filter((h) => h?.startsWith('/e/'));
    expect(hrefs).toEqual(['/e/campus', '/e/davos']);
    expect(screen.getByText(/Ort campus · \d/)).toBeInTheDocument();
    ctx.http.expectNone(() => true);
  });

  it('explains a refused position and keeps the date order', async () => {
    const geo = {
      getCurrentPosition: (_: PositionCallback, fail: PositionErrorCallback) =>
        fail({ code: 1 } as GeolocationPositionError),
    } as Geolocation;
    const ctx = await setup('/karte', geo);
    await respond(ctx, body([FAR, NEAR]));
    await userEvent.click(screen.getByRole('button', { name: 'In meiner Nähe' }));
    ctx.harness.detectChanges();
    expect(
      screen.getByText('Standort nicht verfügbar. Sortiert wird nach Datum.'),
    ).toBeInTheDocument();
  });

  it('says so when the period has no located event and when the list was cut', async () => {
    const ctx = await setup('/karte');
    await respond(ctx, body([]));
    expect(
      screen.getByText('Für diesen Zeitraum gibt es keine Orte mit Koordinaten.'),
    ).toBeInTheDocument();
  });

  it('notes a truncated answer', async () => {
    const ctx = await setup('/karte');
    await respond(ctx, body([FAR], true));
    expect(screen.getByText('Es werden nur die ersten 1 Events gezeigt.')).toBeInTheDocument();
  });

  it('shows the load error with a retry', async () => {
    const ctx = await setup('/karte');
    ctx.http
      .expectOne((r) => r.url === '/api/public/map/events')
      .flush('x', { status: 500, statusText: 'x' });
    ctx.http.match('/api/public/categories').forEach((r) => r.flush(CATEGORIES));
    await ctx.harness.fixture.whenStable();
    ctx.harness.detectChanges();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
