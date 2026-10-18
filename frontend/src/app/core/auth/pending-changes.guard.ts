/**
 * `CanDeactivate` guard for pages with unsaved work. The page owns the question ("Speichern, Verwerfen, Bleiben"
 * is a dialog in its template) and answers through `canLeave`; the guard only asks.
 */
import type { CanDeactivateFn } from '@angular/router';

/** A page that can hold back a navigation. */
export interface PendingChanges {
  /** `true` lets the navigation go on. May open a dialog and resolve when the person has chosen. */
  canLeave(): boolean | Promise<boolean>;
}

export const pendingChangesGuard: CanDeactivateFn<Partial<PendingChanges>> = (component) =>
  component.canLeave ? component.canLeave() : true;
