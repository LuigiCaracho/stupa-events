/** Wire models of the event endpoints (M5b contract 7, camelCase). Written by hand, not generated. */
import type { EventState } from '@shared/status-kind.util';

export type PublicStatus = 'scheduled' | 'cancelled' | 'postponed';
export type ScanStatus = 'pending' | 'clean' | 'infected' | 'error';
export type RightsBasis = 'own_work' | 'permission' | 'license' | 'partner_agreement' | 'unknown';
export type PosterVariant = 'thumb400' | 'card1200';
export type PublicReasonCode =
  'none' | 'room' | 'speaker' | 'illness' | 'registration' | 'weather' | 'other';

/** What the server lets the person do with the dossier now (M5b contract 7.1); the client never works it out. */
export type EventAction =
  | 'publish'
  | 'unpublish'
  | 'archive'
  | 'restore'
  | 'cancel'
  | 'postpone'
  | 'reinstate'
  | 'revert-revision'
  | 'confirm-location'
  | 'verify-howto'
  | 'save-as-format'
  | 'clone';

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
  altText: string | null;
  credit: string | null;
  rightsBasis: RightsBasis;
  derivatives: { thumb400: Derivative; card1200: Derivative; og1200x630: Derivative } | null;
  supersedesId: string | null;
  createdAt: string;
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
  publicReason?: PublicReason | null;
  endEstimated?: boolean;
  primaryCategory: CategoryRef | null;
  poster: Attachment | null;
  rev: number;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  allowedActions: EventAction[];
  editableFields: string[];
  /** Number of `warn` hints (`GET .../hints` lists them). */
  hintCount: number;
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
  /** Only the editorial team, only while the dossier has no organization (M5b contract 7.1). */
  organizationId?: string;
}

export type HintSeverity = 'info' | 'warn';

/** One line of "Fehlt noch" (`GET /api/events/{id}/hints`); the text comes from the catalog, `hints.<code>`. */
export interface Hint {
  code: string;
  severity: HintSeverity;
  field: string | null;
}

export interface HintsOut {
  items: Hint[];
}


export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface PosterMeta {
  altText?: string;
  credit?: string;
  rightsBasis: RightsBasis;
  personsDepicted?: boolean;
  consentNote?: string;
}

