/** Groups, upload kinds and visibility options of the attachment tab (contract 6.3). */
import { type AttachmentKind, RESTRICTED_KINDS, type Visibility } from '../model/attachment.models';

export type AttachmentGroupId = 'poster' | 'social' | 'documents' | 'quotes' | 'other';

export const GROUP_KINDS: Record<AttachmentGroupId, readonly AttachmentKind[]> = {
  poster: ['poster'],
  social: ['social_post'],
  documents: ['business_plan', 'contract'],
  quotes: ['quote'],
  other: ['howto_file', 'other'],
};

export const GROUP_ORDER: readonly AttachmentGroupId[] = [
  'poster',
  'social',
  'documents',
  'quotes',
  'other',
];

/** The kinds a person can pick for a new upload; the poster has its own block in the overview. */
export const UPLOAD_KINDS: readonly AttachmentKind[] = [
  'social_post',
  'business_plan',
  'quote',
  'contract',
  'howto_file',
  'other',
];

export const IMAGE_ONLY_KINDS: readonly AttachmentKind[] = ['poster', 'social_post'];

export const isRestricted = (kind: AttachmentKind): boolean => RESTRICTED_KINDS.includes(kind);

/** "Alle Mitglieder" (`shared`) is never offered for offers, business plans and contracts (PLAN 5.4). */
export const visibilityOptions = (kind: AttachmentKind): readonly Visibility[] =>
  isRestricted(kind) ? ['team', 'org'] : ['team', 'org', 'shared'];

export const isImageFile = (file: File): boolean => file.type.startsWith('image/');

export const groupOf = (kind: AttachmentKind): AttachmentGroupId =>
  GROUP_ORDER.find((g) => GROUP_KINDS[g].includes(kind)) ?? 'other';
