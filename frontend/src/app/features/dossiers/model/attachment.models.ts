/** Wire models of the attachments, comparison quotes and tab counters of a dossier (M4 contract 5.1, 5.8). */
import type { RightsBasis, ScanStatus } from '../api/event.models';

export type AttachmentKind =
  'poster' | 'social_post' | 'business_plan' | 'quote' | 'contract' | 'howto_file' | 'other';

export type Visibility = 'team' | 'org' | 'shared';

/** The kinds that never leave the organization (PLAN 5.4): no "shared" for them. */
export const RESTRICTED_KINDS: readonly AttachmentKind[] = ['business_plan', 'quote', 'contract'];

export interface AttachmentOut {
  id: string;
  kind: AttachmentKind;
  displayName: string;
  mime: string;
  sizeBytes: number;
  visibility: Visibility;
  scanStatus: ScanStatus;
  altText: string | null;
  credit: string | null;
  rightsBasis: RightsBasis | null;
  licenseRef: string | null;
  sourceUrl: string | null;
  personsDepicted: boolean;
  consentNote: string | null;
  containsDate: string | null;
  datedFor: number | null;
  meta: Record<string, unknown>;
  supersedesId: string | null;
  retiredAt: string | null;
  createdAt: string;
  hasPreview: boolean;
  replacedBy: string | null;
}

export interface AttachmentUpload {
  file: File;
  kind: AttachmentKind;
  visibility?: Visibility;
  altText?: string;
  credit?: string;
  rightsBasis?: RightsBasis;
  personsDepicted?: boolean;
  consentNote?: string;
  containsDate?: boolean;
  datedFor?: number;
}

export type AttachmentPatch = Partial<
  Pick<
    AttachmentOut,
    | 'visibility'
    | 'displayName'
    | 'altText'
    | 'credit'
    | 'rightsBasis'
    | 'personsDepicted'
    | 'consentNote'
  >
>;

export interface DossierCounts {
  attachments: number;
  quotes?: number;
  howto: number;
  openChecklist: number;
  mailTemplates: number;
  openComments: number;
}

export interface QuoteOut {
  id: string;
  grp: string;
  vendor: string;
  amountCents: number;
  currency: string;
  validUntil: string | null;
  note: string | null;
  attachmentId: string | null;
  selected: boolean;
  expired: boolean;
  retiredAt: string | null;
}

export interface QuoteGroup {
  grp: string;
  quotes: QuoteOut[];
  cheapestId: string | null;
  selectedId: string | null;
}

export interface QuotesOut {
  groups: QuoteGroup[];
  selectedTotalCents: number;
  selectedTotalCurrency: string;
  suggestedBudgetCents: number | null;
}

export interface QuoteIn {
  grp: string;
  vendor: string;
  amountCents: number;
  currency?: string;
  validUntil?: string;
  note?: string;
  attachmentId?: string;
}
