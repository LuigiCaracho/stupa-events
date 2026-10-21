/** Wire models of the list view of `GET /api/events` (M5b contract 7.1). */
import type { EventState } from '@shared/status-kind.util';
import type { CategoryRef, OrgRef, Page, PublicStatus } from './event.models';

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
  allDay: boolean;
  organization: OrgRef | null;
  venueLabel: string | null;
  primaryCategory: CategoryRef | null;
  hasPoster: boolean;
  createdBy: PersonRef;
  rev: number;
  openQuestions: number;
  formatSlug: string | null;
  /** An archived dossier with a howto nobody checked (M5 contract 3.2). */
  howtoUnverified: boolean;
}

export interface EventQuery {
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
}

export type CardPage = Page<EventCard>;
