/** Wire models of the in-app notifications and the preferences per kind (M4 contract 5.7). */
export const NOTIFICATION_KINDS = ['comment_added', 'published', 'cancelled', 'checklist_due'] as const;
export type NotificationKind = (typeof NOTIFICATION_KINDS)[number];

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
