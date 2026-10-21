/**
 * A one-way channel from outside the dossier page (the palette, Strg+K) to the open dossier: "Als Format speichern".
 * The page reads `pending` in an effect and answers it only if the dossier allows the action, and publishes the
 * `allowedActions` of the open dossier in `allowed`, so the palette lists only the commands it can answer.
 */
import { Injectable, signal } from '@angular/core';

export type DossierCommandName = 'save-as-format';

export interface DossierCommand {
  name: DossierCommandName;
  at: number;
}

@Injectable({ providedIn: 'root' })
export class DossierCommands {
  readonly pending = signal<DossierCommand | null>(null);
  readonly allowed = signal<readonly string[]>([]);

  send(name: DossierCommandName): void {
    this.pending.set({ name, at: Date.now() });
  }

  clear(): void {
    this.pending.set(null);
  }
}
