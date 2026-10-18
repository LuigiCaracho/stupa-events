/** Wire model of `GET /api/tasks` (M3 contract 5.5). */
import type { EventCard, PersonRef } from './board.models';
import type { RevisionOut } from './action.models';

export interface AwaitingCard extends EventCard {
  fourEyesBlocked: boolean;
}

export interface ReturnedCard extends EventCard {
  note: string;
  returnedAt: string;
  returnedBy: PersonRef;
}

export interface ChangedCard extends EventCard {
  baselineRev: number;
  changes: RevisionOut[];
}

export interface TaskCounts {
  awaitingReview: number;
  returned: number;
  due: number;
  mine: number;
  followupOpen: number;
  changedAfterPublish: number;
}

export interface TasksOut {
  awaitingReview: AwaitingCard[];
  returned: ReturnedCard[];
  due: EventCard[];
  mine: EventCard[];
  followupOpen: EventCard[];
  changedAfterPublish: ChangedCard[];
  counts: TaskCounts;
}
