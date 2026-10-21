/** Wire models of the lifecycle bodies, revisions and drafts of a dossier (M5b contract 7.1). */
import type { PersonRef } from './card.models';
import type { EventFields, PublicReasonCode } from './event.models';

export interface CancelBody {
  reason?: string;
  publicReasonCode: PublicReasonCode;
  publicReasonText?: string;
}

export interface PostponeBody extends CancelBody {
  newStartsAt?: string;
  newEndsAt?: string;
}

export interface ReinstateBody {
  reason?: string;
}

export interface RevertBody {
  rev: number;
  note?: string;
}

export interface RevisionOut {
  rev: number;
  at: string;
  actor: PersonRef;
  actorType: 'human' | 'system' | 'agent';
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
