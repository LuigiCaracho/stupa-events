import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { GEOLOCATION, NearMeService } from './near-me.service';

function geo(result: 'ok' | 'denied'): Geolocation {
  return {
    getCurrentPosition: (ok: PositionCallback, fail?: PositionErrorCallback | null) =>
      result === 'ok'
        ? ok({ coords: { latitude: 48.4829, longitude: 9.1873 } } as GeolocationPosition)
        : fail?.({ code: 1 } as GeolocationPositionError),
  } as Geolocation;
}

const service = (g: Geolocation | null): NearMeService => {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: GEOLOCATION, useValue: g },
    ],
  });
  return TestBed.inject(NearMeService);
};

describe('NearMeService', () => {
  it('keeps the position in the signal and sends no request', async () => {
    const near = service(geo('ok'));
    await near.request();
    expect(near.position()).toEqual({ lat: 48.4829, lon: 9.1873 });
    expect(near.status()).toBe('granted');
    TestBed.inject(HttpTestingController).verify();
  });

  it('reports a denial without a position', async () => {
    const near = service(geo('denied'));
    await near.request();
    expect(near.position()).toBeNull();
    expect(near.status()).toBe('denied');
  });

  it('treats a missing API as denied', async () => {
    const near = service(null);
    await near.request();
    expect(near.status()).toBe('denied');
  });

  it('clears the position', async () => {
    const near = service(geo('ok'));
    await near.request();
    near.clear();
    expect(near.position()).toBeNull();
    expect(near.status()).toBe('idle');
  });
});
