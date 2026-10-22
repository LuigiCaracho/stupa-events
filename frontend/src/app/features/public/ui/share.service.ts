/** Copy to the clipboard and share a link: the native share sheet when the browser has one, else the clipboard. */
import { Injectable, inject } from '@angular/core';
import { LOCATION } from '@core/browser/location.token';

export type ShareResult = 'shared' | 'copied' | 'failed';

@Injectable({ providedIn: 'root' })
export class ShareService {
  readonly origin = inject(LOCATION).origin;

  async copy(text: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }

  /** A dismissed share sheet counts as "shared": the person chose, nothing failed. */
  async share(data: { title: string; url: string }): Promise<ShareResult> {
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share(data);
        return 'shared';
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return 'shared';
      }
    }
    return (await this.copy(data.url)) ? 'copied' : 'failed';
  }
}
