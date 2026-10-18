/** Wire models of the actions, revisions and drafts of a dossier (M3 contract 2.4, 4, 5.4, 5.5). */
import type { EventFields, PublicReasonCode } from './event.models';
import type { PersonRef } from './board.models';

export type ActionName =
  | 'cancel'
  | 'postpone'
  | 'reinstate'
  | 'image-exception'
  | 'assign-organization'
  | 'revert-revision'
  | 'acknowledge-changes'
  | 'confirm-flyer'
  /** Hints of `allowedActions` only; they have no route of their own. */
  | 'postpone-with-date'
  | 'public-text';

export interface CancelBody {
  reason: string;
  publicReasonCode: PublicReasonCode;
  publicReasonText?: string;
}

export interface PostponeBody extends CancelBody {
  newStartsAt?: string;
  newEndsAt?: string;
}

export interface ReasonBody {
  reason: string;
}

export interface AssignBody {
  organizationId: string;
}

export interface RevertBody {
  rev: number;
  note?: string;
}

export type ActionBody =
  CancelBody | PostponeBody | ReasonBody | AssignBody | RevertBody | Record<string, never>;

export type FieldClass = 'state' | 'critical' | 'text' | 'dossier';

export interface RevisionOut {
  rev: number;
  at: string;
  actor: PersonRef;
  actorType: 'human' | 'system' | 'agent';
  fieldClass: FieldClass;
  changeNote: string | null;
  changedFields: string[];
}

export interface RevisionDetail extends RevisionOut {
  snapshot: Record<string, unknown>;
}

export interface DraftOut {
  baseRev: number;
  fields: EventFields;
  updatedAt: string;
}
