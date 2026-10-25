/** Whether the browser thinks it has a network: `navigator.onLine` plus the `online` and `offline` events, as a signal. */
import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class OnlineService {
  private readonly win = inject(DOCUMENT).defaultView as Window;
  private readonly _online = signal(this.win.navigator.onLine);

  readonly online = this._online.asReadonly();

  constructor() {
    const set = (value: boolean) => () => this._online.set(value);
    const up = set(true);
    const down = set(false);
    this.win.addEventListener('online', up);
    this.win.addEventListener('offline', down);
    inject(DestroyRef).onDestroy(() => {
      this.win.removeEventListener('online', up);
      this.win.removeEventListener('offline', down);
    });
  }
}
