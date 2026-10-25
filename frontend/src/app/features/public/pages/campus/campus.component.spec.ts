/** Spec for P12 Campuskarte: the counts on map and table agree, the building list opens, the empty days say so. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MapLoaderService } from '@shared/ui/map/map-loader.service';
import { screen, within } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { card, search } from '../../../../../testing/public-fixtures';
import type { PublicCampusCollection } from '../../model/map.models';
import { CampusPageComponent } from './campus.component';

const building = (buildingNo: string, count: number, approx = false) => ({
  type: 'Feature' as const,
  geometry: { type: 'Polygon' as const, coordinates: [] },
  properties: { buildingNo, name: `Gebäude ${buildingNo}`, approx, count },
});

const body = (...b: ReturnType<typeof building>[]): PublicCampusCollection => ({
  type: 'FeatureCollection',
  features: b,
});

async function setup() {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: 'campus', component: CampusPageComponent }]),
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: MapLoaderService, useValue: { load: () => new Promise(() => undefined) } },
    ],
  });
  const harness = await RouterTestingHarness.create();
  await harness.navigateByUrl('/campus', CampusPageComponent);
  harness.detectChanges();
  return { harness, http: TestBed.inject(HttpTestingController) };
}

type Ctx = Awaited<ReturnType<typeof setup>>;

async function respond(ctx: Ctx, data: PublicCampusCollection) {
  ctx.http.expectOne((r) => r.url === '/api/public/campus/buildings').flush(data);
  await ctx.harness.fixture.whenStable();
  ctx.harness.detectChanges();
}

const settle = async (ctx: Ctx) => {
  ctx.harness.detectChanges();
  await new Promise((resolve) => setTimeout(resolve));
};

describe('CampusPageComponent', () => {
  it('asks for the Berlin day and shows the count of building 9 in the table', async () => {
    const ctx = await setup();
    const req = ctx.http.expectOne((r) => r.url === '/api/public/campus/buildings');
    expect(req.request.params.get('from')).toBe(req.request.params.get('to'));
    req.flush(body(building('9', 3), building('2', 0)));
    await ctx.harness.fixture.whenStable();
    ctx.harness.detectChanges();
    const row = screen.getByRole('row', { name: /Gebäude 9/ });
    expect(within(row).getByRole('cell', { name: '3' })).toBeInTheDocument();
  });

  it('opens the event list of a building from the table', async () => {
    const ctx = await setup();
    await respond(ctx, body(building('9', 2)));
    await userEvent.click(screen.getByRole('button', { name: 'Anzeigen' }));
    await settle(ctx);
    const req = ctx.http.expectOne((r) => r.url === '/api/public/campus/events');
    expect(req.request.params.get('building')).toBe('9');
    req.flush(search([card({ slug: 'kino', title: 'Kinoabend' })]));
    await ctx.harness.fixture.whenStable();
    ctx.harness.detectChanges();
    expect(screen.getByText('Gebäude 9: 2 Events')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Kinoabend' })).toBeInTheDocument();
  });

  it('widens the range to seven days for "Diese Woche"', async () => {
    const ctx = await setup();
    await respond(ctx, body(building('9', 1)));
    await userEvent.click(screen.getByRole('radio', { name: /Diese Woche/ }));
    await settle(ctx);
    const req = ctx.http.expectOne((r) => r.url === '/api/public/campus/buildings');
    expect(req.request.params.get('from')).not.toBe(req.request.params.get('to'));
    req.flush(body(building('9', 4)));
  });

  it('says so on a day without events and keeps the table', async () => {
    const ctx = await setup();
    await respond(ctx, body(building('9', 0)));
    expect(screen.getByText('Heute ist auf dem Campus nichts geplant.')).toBeInTheDocument();
    expect(screen.getByRole('row', { name: /Gebäude 9/ })).toBeInTheDocument();
  });

  it('marks an approximate building in the table and the legend', async () => {
    const ctx = await setup();
    await respond(ctx, body(building('17', 1, true)));
    expect(screen.getAllByText('Lage ungefähr').length).toBe(2);
  });

  it('shows the load error', async () => {
    const ctx = await setup();
    ctx.http
      .expectOne((r) => r.url === '/api/public/campus/buildings')
      .flush('x', { status: 500, statusText: 'x' });
    await ctx.harness.fixture.whenStable();
    ctx.harness.detectChanges();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
