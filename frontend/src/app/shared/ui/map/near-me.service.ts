/**
 * "In meiner Nähe", entirely in the browser (decision E30): the position lives in a signal of this service. It is
 * read only to sort the list and to draw one local dot. Nothing here injects `HttpClient`, so no request can carry it.
 */
import { Injectable, InjectionToken, inject, signal } from '@angular/core';
import type { MapPin } from './map.models';

export type NearMeStatus = 'idle' | 'pending' | 'granted' | 'denied';

export const GEOLOCATION = new InjectionToken<Geolocation | null>('GEOLOCATION', {
  factory: () => (typeof navigator !== 'undefined' ? (navigator.geolocation ?? null) : null),
});

@Injectable({ providedIn: 'root' })
export class NearMeService {
  private readonly geolocation = inject(GEOLOCATION);
  private readonly _position = signal<MapPin | null>(null);
  private readonly _status = signal<NearMeStatus>('idle');

  readonly position = this._position.asReadonly();
  readonly status = this._status.asReadonly();

  /** Asks the browser once; call it from a click handler only. */
  request(): Promise<void> {
    const geo = this.geolocation;
    if (!geo) {
      this._status.set('denied');
      return Promise.resolve();
    }
    this._status.set('pending');
    return new Promise((resolve) => {
      geo.getCurrentPosition(
        ({ coords }) => {
          this._position.set({ lat: coords.latitude, lon: coords.longitude });
          this._status.set('granted');
          resolve();
        },
        () => {
          this._position.set(null);
          this._status.set('denied');
          resolve();
        },
        { enableHighAccuracy: false, maximumAge: 60_000, timeout: 10_000 },
      );
    });
  }

  clear(): void {
    this._position.set(null);
    this._status.set('idle');
  }
}
