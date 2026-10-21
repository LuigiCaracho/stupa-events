import { TestBed } from '@angular/core/testing';
import { I18nService } from '@core/i18n/i18n.service';
import type { RevisionOut } from '../api/action.models';
import type { CommentThread } from '../model/comment.models';
import { commentEntries, documentEntries, isStateChange, revisionEntries } from './timeline';

const i18n = () => TestBed.inject(I18nService);

describe('timeline entries', () => {
  it('turns revisions into transitions and edits with their changed fields', () => {
    const revisions = [
      {
        rev: 2,
        at: '2026-10-01T10:00:00Z',
        actor: { sub: 'u', displayName: 'Anna' },
        actorType: 'human',
        changeNote: 'n',
        changedFields: ['state', 'title'],
      },
      {
        rev: 1,
        at: '2026-09-01T10:00:00Z',
        actor: { sub: 's', displayName: null },
        actorType: 'system',
        changeNote: null,
        changedFields: [],
      },
    ] as unknown as RevisionOut[];
    const entries = revisionEntries(i18n(), revisions);
    expect(entries[0]).toMatchObject({
      icon: 'flow',
      title: 'Statuswechsel (Fassung 2)',
      actor: 'Anna',
      body: 'n',
    });
    expect(entries[0].changes?.map((c) => c.label)).toEqual(['Zustand', 'Titel']);
    expect(entries[1]).toMatchObject({
      icon: 'edit',
      title: 'Fassung 1 gespeichert',
      actor: 'System',
    });
  });

  it('knows a state change by the field "state" in its snapshot diff', () => {
    expect(isStateChange({ changedFields: ['state'] } as RevisionOut)).toBe(true);
    expect(isStateChange({ changedFields: ['summary'] } as RevisionOut)).toBe(false);
  });

  it('turns document revisions into entries', () => {
    const entries = documentEntries(i18n(), [
      {
        rev: 3,
        actorId: null,
        actorType: 'system',
        changeNote: 'x',
        at: '2026-10-01T10:00:00Z',
        titleChanged: false,
        charsDelta: 4,
      },
      {
        rev: 2,
        actorId: 'u',
        actorType: 'human',
        changeNote: null,
        at: '2026-10-01T09:00:00Z',
        titleChanged: false,
        charsDelta: 1,
      },
    ]);
    expect(entries[0]).toMatchObject({ title: 'Anleitung, Fassung 3', actor: 'System' });
    expect(entries[1].actor).toBeNull();
  });

  it('turns threads into question, reply and resolved entries', () => {
    const reply = { id: 'r', authorName: 'B', createdAt: '2026-10-02T10:00:00Z', bodyMd: 'ok' };
    const threads = [
      {
        id: 't',
        authorName: 'A',
        createdAt: '2026-10-01T10:00:00Z',
        bodyMd: 'q',
        resolvedAt: '2026-10-03T10:00:00Z',
        replies: [reply],
      },
      {
        id: 'u',
        authorName: 'A',
        createdAt: '2026-10-01T11:00:00Z',
        bodyMd: 'q2',
        resolvedAt: null,
        replies: [],
      },
    ] as unknown as CommentThread[];
    expect(commentEntries(i18n(), threads).map((e) => e.title)).toEqual([
      'Rückfrage',
      'Antwort',
      'Rückfrage erledigt',
      'Rückfrage',
    ]);
  });
});
