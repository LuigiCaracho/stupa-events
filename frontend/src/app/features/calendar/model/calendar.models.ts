/** Wire models of `GET /api/events?view=calendar` (M5 contract 7), camelCase, written by hand. */
import type { EventState } from '@shared/status-kind.util';
import type { PublicStatus } from '../../dossiers/api/event.models';

export interface CalendarEntry {
  id: string;
  title: string;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  startsOn: string | null;
  endsOn: string | null;
  state: EventState;
  publicStatus: PublicStatus;
  organization: { slug: string; short: string; colorToken: string | null } | null;
  category: { slug: string; colorToken: string | null } | null;
  venueName: string | null;
  howtoUnverified: boolean;
}

export interface CalendarOut {
  from: string;
  to: string;
  entries: CalendarEntry[];
  truncated: boolean;
}

export interface CalendarQuery {
  from: string;
  to: string;
  state?: readonly string[];
  organization?: string;
  category?: string;
  mine?: boolean;
  q?: string;
}
