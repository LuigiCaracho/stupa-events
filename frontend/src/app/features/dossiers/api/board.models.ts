/** Wire models of the list and board views of `GET /api/events` (M3 contract 5.1). */
import type { ProblemReason } from '@core/api/models';
import type { EventState } from '@shared/status-kind.util';
import type { CategoryRef, OrgRef, Page, PublicStatus, TransitionId } from './event.models';

export type ColumnKey =
  'idea' | 'planning' | 'in_review' | 'published' | 'followup' | 'archived' | 'withdrawn';

/** The board column that shows a state; `approved` and `live` share "Veröffentlicht". */
export const COLUMN_OF_STATE: Record<EventState, ColumnKey> = {
  idea: 'idea',
  planning: 'planning',
  in_review: 'in_review',
  approved: 'published',
  live: 'published',
  followup: 'followup',
  archived: 'archived',
  withdrawn: 'withdrawn',
};

export interface PersonRef {
  sub: string;
  displayName: string | null;
}

export interface EventCard {
  id: string;
  title: string;
  state: EventState;
  publicStatus: PublicStatus;
  startsAt: string;
  endsAt: string;
  tzid: string;
  organization: OrgRef | null;
  venueLabel: string | null;
  primaryCategory: CategoryRef | null;
  publishAt: string | null;
  hasPoster: boolean;
  createdBy: PersonRef;
  rev: number;
  allowedTransitions: TransitionId[];
  nextTransition: TransitionId | null;
  blockers: ProblemReason[];
  blockerCount: number;
  moves: Partial<Record<ColumnKey, TransitionId>>;
  openQuestions: number;
}

export interface BoardColumn {
  key: ColumnKey;
  states: EventState[];
  total: number;
  items: EventCard[];
  truncated: boolean;
}

export interface BoardOut {
  columns: BoardColumn[];
  generatedAt: string;
}

export interface EventQuery {
  view?: 'list' | 'board';
  state?: readonly EventState[];
  organization?: string;
  category?: string;
  mine?: boolean;
  q?: string;
  from?: string;
  to?: string;
  sort?: 'startsAt' | '-startsAt';
  limit?: number;
  offset?: number;
  columnLimit?: number;
}

export type CardPage = Page<EventCard>;
