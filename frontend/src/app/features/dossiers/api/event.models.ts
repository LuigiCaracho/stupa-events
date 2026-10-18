/** Wire models of the event endpoints (M1 contract 4.2, camelCase). Written by hand, not generated. */
import type { ProblemReason } from '@core/api/models';
import type { EventState } from '@shared/status-kind.util';

export type TransitionId = 'T01' | 'T02' | 'T04' | 'T05';
export type PublicStatus = 'scheduled' | 'cancelled' | 'postponed';
export type ScanStatus = 'pending' | 'clean' | 'infected' | 'error';
export type RightsBasis = 'own_work' | 'permission' | 'license' | 'partner_agreement' | 'unknown';
export type PosterVariant = 'thumb400' | 'card1200';

export interface OrgRef {
  id: string;
  slug: string;
  name: string;
  short: string;
}

export interface CategoryRef {
  id: string;
  slug: string;
  name: string;
  kind: 'format' | 'fachschaft' | 'partner';
  parentId?: string | null;
  /** Present on the tree answer (`GET /api/categories?tree=true`). */
  children?: CategoryRef[];
}

export interface Derivative {
  id: string;
  width: number;
  height: number;
}

export interface Attachment {
  id: string;
  eventId: string;
  kind: 'poster';
  displayName: string;
  mime: string;
  sizeBytes: number;
  sha256: string;
  scanStatus: ScanStatus;
  altText: string;
  credit: string;
  rightsBasis: RightsBasis;
  derivatives: { thumb400: Derivative; card1200: Derivative; og1200x630: Derivative } | null;
  supersedesId: string | null;
  createdAt: string;
}

export interface ImageException {
  grantedBy: string;
  reason: string;
  at: string;
}

export interface EventDto {
  id: string;
  slug: string | null;
  state: EventState;
  publicStatus: PublicStatus;
  title: string;
  summary: string | null;
  descriptionMd: string | null;
  startsAt: string;
  endsAt: string;
  tzid: string;
  allDay: boolean;
  organization: OrgRef | null;
  venueText: string | null;
  primaryCategory: CategoryRef | null;
  poster: Attachment | null;
  imageException: ImageException | null;
  rev: number;
  createdBy: string;
  submittedBy: string | null;
  approvedBy: string | null;
  createdAt: string;
  updatedAt: string;
  allowedTransitions: TransitionId[];
}

export interface EventCreate {
  title: string;
  startsAt: string;
  endsAt: string;
  tzid: string;
  allDay: boolean;
  organizationId: string;
  venueText?: string;
  primaryCategoryId?: string;
  summary?: string;
  descriptionMd?: string;
}

export interface EventPatch {
  rev: number;
  title?: string;
  startsAt?: string;
  endsAt?: string;
  allDay?: boolean;
  venueText?: string;
  primaryCategoryId?: string;
  summary?: string;
  descriptionMd?: string;
}

export type Reason = ProblemReason;

export interface GuardResult {
  transition: TransitionId;
  allowed: boolean;
  reasons: Reason[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventQuery {
  state?: EventState;
  organizationId?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface PosterMeta {
  altText: string;
  credit: string;
  rightsBasis: RightsBasis;
}
