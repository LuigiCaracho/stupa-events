/** Wire models of search, templates, cloning and "Letztes Mal" (M5 contract 4 and 6, camelCase, written by hand). */
import type { EventState } from '@shared/status-kind.util';
import type { EventDto, FormatRef, OrgBrief } from '../../dossiers/api/event.models';

export type SearchScope = 'events' | 'documents' | 'formats';
export type HitKind = 'event' | 'document' | 'format';

export interface HitSegment {
  text: string;
  hit: boolean;
}

export interface HitHighlight {
  field: string;
  segments: HitSegment[];
}

export interface SearchHit {
  kind: HitKind;
  id: string;
  title: string;
  subtitle: string;
  state?: EventState;
  startsAt?: string;
  organization: { slug: string; short: string } | null;
  format: FormatRef | null;
  howtoVerifiedAt?: string | null;
  howtoUnverified?: boolean;
  foreign: boolean;
  link: string;
  rank: number;
  highlights: HitHighlight[];
}

export interface Facet {
  value: string;
  label: string;
  count: number;
}

export interface SearchFacets {
  state: Facet[];
  organization: Facet[];
  year: Facet[];
  category: Facet[];
  format: Facet[];
}

export interface SearchOut {
  q: string;
  scope: SearchScope;
  total: number;
  hits: SearchHit[];
  facets: SearchFacets;
  suggestion: string | null;
}

export interface SearchQuery {
  q: string;
  scope?: SearchScope;
  state?: readonly string[];
  org?: string;
  year?: string;
  category?: string;
  format?: string;
  limit?: number;
  offset?: number;
}

export interface TemplateCard {
  id: string;
  title: string;
  startsAt: string;
  allDay: boolean;
  state: EventState;
  organization: OrgBrief;
  format: FormatRef | null;
  categories: { slug: string; name: string }[];
  attendance: number | null;
  howtoVerifiedAt: string | null;
  howtoUnverified: boolean;
  hasHowto: boolean;
  foreign: boolean;
  sharedDocuments: number;
  checklistItems: number;
}

export interface TemplatePage {
  items: TemplateCard[];
  total: number;
  limit: number;
  offset: number;
}

export interface TemplateQuery {
  q?: string;
  category?: string;
  organization?: string;
  format?: string;
  year?: string;
  limit?: number;
  offset?: number;
}

/** What happens to one part of the template (the lines of `CARRY_OVER`, M5 contract 4.2): copied, reset, partly copied, linked or never. */
export type CarryMode = 'copy' | 'reset' | 'partial' | 'link' | 'never';

export interface CarryOverLine {
  part: string;
  mode: CarryMode;
  /** An i18n key, `clone.reason.<name>`. */
  reason: string;
  count?: number | null;
}

export interface CloneIn {
  startsAt: string;
  endsAt?: string;
  organizationId?: string;
  title?: string;
}

export interface CloneOut {
  event: EventDto;
  report: CarryOverLine[];
  checklistRecomputed?: number;
}

export interface LastTimeSource {
  id: string;
  title: string;
  startsAt: string;
  state: EventState;
  organization: { slug: string; short: string };
  own: boolean;
}

export interface LastTime {
  source: LastTimeSource;
  attendance: number | null;
  costsCents: number | null;
  revenueCents: number | null;
  notes: string | null;
  retrospective: { id: string; rev: number; bodyMd: string } | null;
  restricted: boolean;
}

export interface ClonePreview {
  report: CarryOverLine[];
  lastTime: LastTime | null;
}

export interface ArchiveDocumentRef {
  id: string;
  title: string;
  kind: string;
  verifiedAt: string | null;
}

export interface ArchiveAttachmentRef {
  id: string;
  displayName: string;
  kind: string;
  mime: string;
  sizeBytes: number;
}

/** `GET /api/archive/{id}`: the core data of an archived dossier and what it shares (M5 contract 4.1). */
export interface ArchiveEventOut {
  id: string;
  title: string;
  summary: string | null;
  descriptionMd: string | null;
  state: EventState;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  organization: OrgBrief;
  category: { slug: string; name: string } | null;
  format: FormatRef | null;
  venueName: string | null;
  attendance: number | null;
  documents: ArchiveDocumentRef[];
  attachments: ArchiveAttachmentRef[];
  own: boolean;
}
