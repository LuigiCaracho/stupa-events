/** Wire models of documents (howto), their revisions and diffs, and mail templates (M4 contract 5.2, 5.6). */
import type { Visibility } from './attachment.models';

export type DocumentKind = 'howto' | 'notes' | 'mail_template';

export interface DocumentOut {
  id: string;
  kind: DocumentKind;
  title: string;
  visibility: Visibility;
  carryOver: boolean;
  rev: number;
  verifiedAt: string | null;
  verifiedBy: string | null;
  updatedAt: string;
  bodyMd?: string;
  meta?: Record<string, unknown>;
}

export interface DocumentIn {
  kind: 'howto' | 'notes';
  title: string;
  bodyMd?: string;
  visibility?: Visibility;
  carryOver?: boolean;
}

export interface DocumentPut {
  title?: string;
  bodyMd: string;
  changeNote?: string;
  visibility?: Visibility;
  carryOver?: boolean;
}

export interface DocumentRevisionOut {
  rev: number;
  actorId: string | null;
  actorType: string;
  changeNote: string | null;
  at: string;
  titleChanged: boolean;
  charsDelta: number;
}

export interface DiffLine {
  op: 'equal' | 'add' | 'remove';
  text: string;
  fromLine: number | null;
  toLine: number | null;
}

export interface DiffOut {
  from: number;
  to: number;
  lines: DiffLine[];
  added: number;
  removed: number;
}

export interface DocumentDraft {
  bodyMd: string;
  baseRev: number;
  updatedAt: string;
}

export interface MailTemplateSummary {
  id: string;
  title: string;
  subject: string;
  visibility: Visibility;
  rev: number;
  updatedAt: string;
}

export interface MailTemplateOut extends MailTemplateSummary {
  bodyMd: string;
  meta: Record<string, unknown>;
}

export interface MailTemplatePut {
  title?: string;
  subject: string;
  toHint?: string;
  bodyMd: string;
  changeNote?: string;
}

export interface PlaceholderOut {
  path: string;
  label: string;
  example: string;
}

export interface RenderedMail {
  subject: string;
  body: string;
}
