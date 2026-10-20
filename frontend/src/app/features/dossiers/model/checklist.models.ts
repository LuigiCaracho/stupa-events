/** Wire models of the checklist of a dossier (M4 contract 5.3). */
export type ChecklistPhase = 'planning' | 'review' | 'live' | 'followup';

export const CHECKLIST_PHASES: readonly ChecklistPhase[] = [
  'planning',
  'review',
  'live',
  'followup',
];

export interface ChecklistItemOut {
  id: string;
  text: string;
  phase: ChecklistPhase;
  required: boolean;
  position: number;
  assigneeSub: string | null;
  assigneeName: string | null;
  dueAt: string | null;
  dueOffsetDays: number | null;
  dueManual: boolean;
  overdue: boolean;
  doneAt: string | null;
  doneBy: string | null;
  waivedReason: string | null;
  fromTemplate: boolean;
}

export interface ChecklistOut {
  items: ChecklistItemOut[];
  openRequired: Record<ChecklistPhase, number>;
  template: { slug: string; name: string } | null;
  added?: number;
}

export interface ChecklistItemIn {
  text: string;
  phase: ChecklistPhase;
  required?: boolean;
  assigneeSub?: string;
  dueAt?: string;
}

export interface ChecklistItemPatch {
  text?: string;
  phase?: ChecklistPhase;
  required?: boolean;
  assigneeSub?: string | null;
  dueAt?: string | null;
  waivedReason?: string | null;
  position?: number;
}
