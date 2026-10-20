/** Builds the entries of the I12 timeline from event revisions, document revisions and comments (pure functions). */
import type { I18nService } from '@core/i18n/i18n.service';
import { fieldLabel } from '@shared/ui/guard-list/reason-text';
import type { HistoryEntry } from '@shared/ui/history/history.component';
import type { RevisionOut } from '../api/action.models';
import type { CommentThread } from '../model/comment.models';
import type { DocumentRevisionOut } from '../model/document.models';

export function revisionEntries(
  i18n: I18nService,
  revisions: readonly RevisionOut[],
): HistoryEntry[] {
  return revisions.map((r) => ({
    at: r.at,
    icon: r.fieldClass === 'state' ? 'flow' : 'edit',
    title:
      r.fieldClass === 'state'
        ? i18n.translate('activity.transition', { rev: r.rev })
        : i18n.translate('activity.revision', { rev: r.rev }),
    actor: r.actorType === 'system' ? i18n.translate('history.system') : r.actor.displayName,
    body: r.changeNote,
    changes: r.changedFields.map((f) => ({
      kind: 'warn' as const,
      tag: i18n.translate('activity.changed'),
      label: fieldLabel(i18n, f),
    })),
  }));
}

export function documentEntries(
  i18n: I18nService,
  revisions: readonly DocumentRevisionOut[],
): HistoryEntry[] {
  return revisions.map((r) => ({
    at: r.at,
    icon: 'document',
    title: i18n.translate('activity.howtoRevision', { rev: r.rev }),
    actor: r.actorType === 'system' ? i18n.translate('history.system') : null,
    body: r.changeNote,
  }));
}

export function commentEntries(
  i18n: I18nService,
  threads: readonly CommentThread[],
): HistoryEntry[] {
  return threads.flatMap((t) => [
    {
      at: t.createdAt,
      icon: 'chat' as const,
      title: i18n.translate('activity.question'),
      actor: t.authorName,
      body: t.bodyMd,
    },
    ...t.replies.map((r) => ({
      at: r.createdAt,
      icon: 'chat' as const,
      title: i18n.translate('activity.reply'),
      actor: r.authorName,
      body: r.bodyMd,
    })),
    ...(t.resolvedAt
      ? [
          {
            at: t.resolvedAt,
            icon: 'check' as const,
            title: i18n.translate('activity.resolved'),
            actor: null,
            body: null,
          },
        ]
      : []),
  ]);
}
