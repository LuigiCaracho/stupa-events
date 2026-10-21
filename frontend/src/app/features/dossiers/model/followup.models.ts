/** Wire models of the follow-up of a dossier: result of an edition (M5 contract 3.4, 3.6, 4.5). */
import type { Outcome } from '../api/event.models';

/** Body of `PUT /api/events/{id}/outcome`; `waived` clears the three numbers. */
export interface OutcomeIn {
  attendance: number | null;
  costsCents: number | null;
  revenueCents: number | null;
  notes: string | null;
  waived: boolean;
  waivedReason: string | null;
}

export const EMPTY_OUTCOME: Outcome = {
  attendance: null,
  costsCents: null,
  revenueCents: null,
  notes: null,
  waived: false,
  waivedReason: null,
};
