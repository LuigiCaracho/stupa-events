/** Test fixtures of the dossier specs: a complete event DTO and a fake `EventsApi`. */
import { of } from 'rxjs';
import type { MeOrganization } from '../app/core/api/models';
import type { BoardColumn, ColumnKey, EventCard } from '../app/features/dossiers/api/board.models';
import type { EventDto, GuardResult, OrgRef } from '../app/features/dossiers/api/event.models';
import type { TasksOut } from '../app/features/dossiers/api/task.models';

export const FSI: OrgRef = {
  id: 'org-fsi',
  slug: 'fsi',
  name: 'Fachschaft Informatik',
  short: 'FSI',
};

export const FSI_MEMBERSHIP: MeOrganization = {
  slug: 'fsi',
  role: 'organizer',
  organizationId: 'org-fsi',
  name: 'Fachschaft Informatik',
  short: 'FSI',
  trusted: false,
};

export function makeEvent(overrides: Partial<EventDto> = {}): EventDto {
  return {
    id: 'ev-1',
    slug: null,
    state: 'planning',
    publicStatus: 'scheduled',
    title: 'Movienight',
    summary: 'Film und Popcorn',
    descriptionMd: null,
    startsAt: '2026-11-05T18:00:00Z',
    endsAt: '2026-11-05T21:00:00Z',
    tzid: 'Europe/Berlin',
    allDay: false,
    organization: FSI,
    venueText: 'Kinosaal 9-133',
    primaryCategory: { id: 'cat-1', slug: 'kino', name: 'Kino', kind: 'format' },
    poster: null,
    imageException: null,
    rev: 3,
    createdBy: 'u1',
    submittedBy: null,
    approvedBy: null,
    createdAt: '2026-10-01T10:00:00Z',
    updatedAt: '2026-10-02T10:00:00Z',
    allowedTransitions: ['T02'],
    ...overrides,
  };
}

export function makeCard(overrides: Partial<EventCard> = {}): EventCard {
  return {
    id: 'ev-1',
    title: 'Movienight',
    state: 'planning',
    publicStatus: 'scheduled',
    startsAt: '2026-11-05T18:00:00Z',
    endsAt: '2026-11-05T21:00:00Z',
    tzid: 'Europe/Berlin',
    organization: FSI,
    venueLabel: 'Kinosaal 9-133',
    primaryCategory: null,
    publishAt: null,
    hasPoster: false,
    createdBy: { sub: 'u1', displayName: 'Mara Keller' },
    rev: 3,
    allowedTransitions: ['T02'],
    nextTransition: 'T02',
    blockers: [],
    blockerCount: 0,
    moves: { in_review: 'T02' },
    openQuestions: 0,
    ...overrides,
  };
}

export function makeColumn(
  key: ColumnKey,
  items: EventCard[] = [],
  overrides: Partial<BoardColumn> = {},
): BoardColumn {
  const states: Record<ColumnKey, BoardColumn['states']> = {
    idea: ['idea'],
    planning: ['planning'],
    in_review: ['in_review'],
    published: ['approved', 'live'],
    followup: ['followup'],
    archived: ['archived'],
    withdrawn: ['withdrawn'],
  };
  return { key, states: states[key], total: items.length, items, truncated: false, ...overrides };
}

export function makeTasks(overrides: Partial<TasksOut> = {}): TasksOut {
  const empty = {
    awaitingReview: [],
    returned: [],
    due: [],
    mine: [],
    followupOpen: [],
    changedAfterPublish: [],
  };
  return {
    ...empty,
    counts: {
      awaitingReview: 0,
      returned: 0,
      due: 0,
      mine: 0,
      followupOpen: 0,
      changedAfterPublish: 0,
    },
    ...overrides,
  };
}

export function makeGuards(overrides: Partial<GuardResult> = {}): GuardResult {
  return { transition: 'T02', allowed: true, reasons: [], ...overrides };
}

export function fakeApi(overrides: Record<string, unknown> = {}) {
  return {
    listCards: jest.fn(() => of({ items: [makeCard()], total: 1, limit: 100, offset: 0 })),
    board: jest.fn(() =>
      of({
        columns: [
          makeColumn('idea'),
          makeColumn('planning', [makeCard()]),
          makeColumn('in_review'),
          makeColumn('published'),
          makeColumn('followup'),
        ],
        generatedAt: '2026-10-18T10:00:00Z',
      }),
    ),
    tasks: jest.fn(() => of(makeTasks())),
    get: jest.fn(() => of(makeEvent())),
    create: jest.fn(() => of(makeEvent({ state: 'idea' }))),
    patch: jest.fn(() => of(makeEvent())),
    transition: jest.fn(() => of(makeEvent({ state: 'in_review' }))),
    action: jest.fn(() => of(makeEvent())),
    draft: jest.fn(() => of(null)),
    saveDraft: jest.fn(() => of({ baseRev: 3, fields: {}, updatedAt: '2026-10-18T10:00:00Z' })),
    discardDraft: jest.fn(() => of(undefined)),
    revisions: jest.fn(() => of({ items: [], total: 0, limit: 50, offset: 0 })),
    revision: jest.fn(() => of({ rev: 3, snapshot: {} })),
    guards: jest.fn(() => of(makeGuards())),
    uploadPoster: jest.fn(() => of({})),
    posterUrl: jest.fn((id: string) => `/api/events/${id}/poster/file?variant=thumb400`),
    organizations: jest.fn(() => of([FSI])),
    allOrganizations: jest.fn(() => of([FSI])),
    venues: jest.fn(() => of([{ id: 'v1', slug: 'kino', name: 'Kinosaal' }])),
    categories: jest.fn(() => of([{ id: 'cat-1', slug: 'kino', name: 'Kino', kind: 'format' }])),
    ...overrides,
  };
}

export function fakeAuth(overrides: Record<string, unknown> = {}) {
  return {
    organizations: () => [{ slug: 'fsi', role: 'organizer' }],
    userId: () => 'u1',
    can: () => false,
    ...overrides,
  };
}
