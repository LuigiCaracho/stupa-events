/** Wire models of the event endpoints (M1 contract 4.2, M3 contract 5.1, camelCase). Written by hand, not generated. */
import type { ProblemReason } from '@core/api/models';
import type { EventState } from '@shared/status-kind.util';

export const TRANSITION_IDS = [
  'T01',
  'T02',
  'T03',
  'T04',
  'T05',
  'T06',
  'T07',
  'T08',
  'T08b',
  'T09',
  'T09b',
  'T10',
  'T11',
  'T12',
] as const;

export type TransitionId = (typeof TRANSITION_IDS)[number];
export type PublicStatus = 'scheduled' | 'cancelled' | 'postponed';
export type ScanStatus = 'pending' | 'clean' | 'infected' | 'error';
export type RightsBasis = 'own_work' | 'permission' | 'license' | 'partner_agreement' | 'unknown';
export type PosterVariant = 'thumb400' | 'card1200';
export type PublicReasonCode =
  'none' | 'room' | 'speaker' | 'illness' | 'registration' | 'weather' | 'other';
export type LockReason = 'in_review' | 'approved' | 'live_critical' | 'closed';

export interface OrgRef {
  id: string;
  slug: string;
  name: string;
  short: string;
}

export type RequiredProfile = 'generic' | 'party' | 'meeting' | 'trip';
export type LocationPrecision = 'hidden' | 'building' | 'exact';

/** The result of an edition (M5 contract 3.5); amounts in cents, EUR. */
export interface Outcome {
  attendance: number | null;
  costsCents: number | null;
  revenueCents: number | null;
  notes: string | null;
  waived: boolean;
  waivedReason: string | null;
}

/** Slug, name and short name of an organization (the `OrgBrief` of the formats and the archive). */
export interface OrgBrief {
  slug: string;
  name: string;
  short: string;
}

export interface FormatRef {
  slug: string;
  title: string;
}

export interface CategoryRef {
  id: string;
  slug: string;
  name: string;
  kind: 'format' | 'fachschaft' | 'partner';
  parentId?: string | null;
  requiredProfile?: RequiredProfile;
  /** Present on the tree answer (`GET /api/categories?tree=true`). */
  children?: CategoryRef[];
}

export interface VenueRef {
  id: string;
  slug: string;
  name: string;
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

export interface PublicReason {
  code: PublicReasonCode;
  text: string | null;
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
  venueId?: string | null;
  venue?: VenueRef | null;
  venueText: string | null;
  costText?: string | null;
  ticketUrl?: string | null;
  websiteUrl?: string | null;
  publishAt?: string | null;
  publicReason?: PublicReason | null;
  endEstimated?: boolean;
  textReviewedRev?: number;
  publishedRev?: number | null;
  flyerCheckedAt?: string | null;
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
  allowedActions?: string[];
  editableFields?: string[];
  lockReason?: LockReason | null;
  /** Set on the answer of a save that moved the start: how many checklist due dates were recomputed. */
  checklistRecomputed?: number;
  outcome?: Outcome | null;
  howtoVerifiedAt?: string | null;
  howtoVerifiedBy?: string | null;
  /** An archived dossier with a howto nobody checked (M5 contract 3.2). */
  howtoUnverified?: boolean;
  formatId?: string | null;
  format?: FormatRef | null;
  derivedFromId?: string | null;
  facts?: Record<string, unknown> | null;
  locationPrecision?: LocationPrecision;
  locationConfirmedAt?: string | null;
}

export interface EventCreate {
  title: string;
  startsAt: string;
  endsAt?: string;
  tzid: string;
  allDay: boolean;
  organizationId?: string;
  venueId?: string;
  venueText?: string;
  primaryCategoryId?: string;
  summary?: string;
  descriptionMd?: string;
}

/** The fields `PATCH` and `PUT .../draft` accept (M3 contract 3.1); `rev` travels in `If-Match`. */
export interface EventFields {
  title?: string;
  startsAt?: string;
  endsAt?: string;
  allDay?: boolean;
  venueId?: string | null;
  venueText?: string | null;
  primaryCategoryId?: string | null;
  ticketUrl?: string | null;
  websiteUrl?: string | null;
  summary?: string | null;
  descriptionMd?: string | null;
  costText?: string | null;
}

export interface EventPatch extends EventFields {
  note?: string;
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

export interface PosterMeta {
  altText: string;
  credit: string;
  rightsBasis: RightsBasis;
  personsDepicted?: boolean;
  consentNote?: string;
}

export interface TransitionIn {
  note?: string;
  publishAt?: string;
}
