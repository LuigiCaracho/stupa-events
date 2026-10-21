/**
 * State of the command palette: open or closed, and whether it was ever asked for. The shell loads the palette component
 * (a lazy chunk with the search client) with `@defer (when requested())`, so the initial bundle only carries this service
 * and the shortcut.
 */
import { Injectable, signal } from '@angular/core';
import { isPaletteShortcut } from './shortcut';

@Injectable({ providedIn: 'root' })
export class PaletteService {
  readonly isOpen = signal(false);
  readonly requested = signal(false);

  show(): void {
    this.requested.set(true);
    this.isOpen.set(true);
  }

  hide(): void {
    this.isOpen.set(false);
  }

  toggle(): void {
    if (this.isOpen()) this.hide();
    else this.show();
  }

  /** Handles a key press of the page: Strg/Cmd+K toggles the palette. */
  onKey(event: KeyboardEvent): void {
    if (!isPaletteShortcut(event)) return;
    event.preventDefault();
    this.toggle();
  }
}
