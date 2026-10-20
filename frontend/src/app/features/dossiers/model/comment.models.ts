/** Wire models of comment threads and their anchors (M4 contract 2.3, 5.5). */
export type CommentAnchor =
  | { field: string }
  | { attachmentId: string }
  | { checklistItemId: string }
  | { documentId: string; rev: number; from: number; to: number };

export interface CommentOut {
  id: string;
  authorSub: string;
  authorName: string;
  actorType: string;
  bodyMd: string;
  anchor: CommentAnchor | null;
  parentId: string | null;
  resolvedAt: string | null;
  resolvedBy: string | null;
  createdAt: string;
}

export interface CommentThread extends CommentOut {
  replies: CommentOut[];
}

export interface CommentIn {
  bodyMd: string;
  anchor?: CommentAnchor;
  parentId?: string;
}
