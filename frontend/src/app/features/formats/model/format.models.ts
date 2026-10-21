/** Wire models of formats (M5 contract 4.4), camelCase, written by hand. */
import type { EventState } from '@shared/status-kind.util';
import type { EventDto, OrgBrief } from '../../dossiers/api/event.models';

export interface FormatEditionRef {
  id: string;
  title: string;
  startsAt: string;
}

export interface FormatCard {
  slug: string;
  title: string;
  organization: OrgBrief;
  active: boolean;
  lastVerifiedAt: string | null;
  howtoStale: boolean;
  editions: number;
  lastEdition: FormatEditionRef | null;
}

export interface FormatPage {
  items: FormatCard[];
  total: number;
  limit: number;
  offset: number;
}

export interface MasterHowto {
  id: string;
  rev: number;
  title: string;
  verifiedAt: string | null;
  verifiedBy: string | null;
  bodyMd: string;
}

export interface FormatEdition {
  id: string;
  title: string;
  startsAt: string;
  state: EventState;
  attendance: number | null;
  costsCents: number | null;
  howtoUnverified: boolean;
  foreign: boolean;
}

export interface FormatChecklistItem {
  text: string;
  phase: string;
  required: boolean;
  dueOffsetDays: number | null;
}

export interface FormatMailRef {
  id: string;
  title: string;
  eventId: string;
}

export interface FormatDefaults {
  categoryId?: string | null;
  venueId?: string | null;
  durationMinutes?: number | null;
  checklistProfile?: 'generic' | 'party' | 'meeting' | 'trip' | null;
}

export interface FormatOut extends Omit<FormatCard, 'editions'> {
  lastVerifiedBy: string | null;
  defaults: FormatDefaults;
  descriptionMd: string | null;
  masterHowto: MasterHowto | null;
  checklist: {
    profile: string;
    template: { slug: string; name: string } | null;
    items: FormatChecklistItem[];
  };
  mailTemplates: FormatMailRef[];
  editions: FormatEdition[];
}

export interface FormatCreate {
  slug: string;
  title: string;
  organizationId: string;
  defaults?: FormatDefaults;
  descriptionMd?: string;
}

export interface FormatPatch {
  title?: string;
  defaults?: FormatDefaults;
  descriptionMd?: string;
  active?: boolean;
}

export interface NewEditionIn {
  startsAt: string;
  endsAt?: string;
  organizationId?: string;
}

export interface SaveAsFormatIn {
  slug: string;
  title: string;
  defaults?: FormatDefaults;
}

export type NewEditionOut = { event: EventDto; report: unknown[] };
