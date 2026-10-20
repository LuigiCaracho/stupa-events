/** Wire models of the in-app notifications and the preferences per kind (M4 contract 5.7). */
export type NotificationKind =
  | 'review_requested'
  | 'changes_requested'
  | 'comment_added'
  | 'comment_resolved'
  | 'transition_done'
  | 'task_assigned'
  | 'checklist_due';

export interface NotificationOut {
  id: string;
  kind: NotificationKind;
  eventId: string | null;
  eventTitle: string | null;
  params: Record<string, unknown>;
  link: string;
  createdAt: string;
  readAt: string | null;
}

export interface NotificationPage {
  items: NotificationOut[];
  nextCursor: string | null;
}

export interface NotificationPref {
  kind: NotificationKind;
  inApp: boolean;
  mail: boolean;
  mailAvailable: boolean;
  essential: boolean;
}

export interface NotificationPrefIn {
  kind: NotificationKind;
  inApp: boolean;
  mail: boolean;
}
