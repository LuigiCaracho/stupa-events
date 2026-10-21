/** Test fixtures of the dossier specs: a complete event DTO and a fake `EventsApi`. */
import { of } from 'rxjs';
import type { MeOrganization } from '../app/core/api/models';
import type { EventCard } from '../app/features/dossiers/api/card.models';
import type { EventDto, OrgRef } from '../app/features/dossiers/api/event.models';

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
};

export function makeEvent(overrides: Partial<EventDto> = {}): EventDto {
  return {
    id: 'ev-1',
    slug: null,
    state: 'draft',
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
    rev: 3,
    createdBy: 'u1',
    createdAt: '2026-10-01T10:00:00Z',
    updatedAt: '2026-10-02T10:00:00Z',
    allowedActions: ['publish', 'archive', 'clone'],
    editableFields: [
      'title',
      'summary',
      'descriptionMd',
      'costText',
      'startsAt',
      'endsAt',
      'venueId',
      'venueText',
      'primaryCategoryId',
      'ticketUrl',
      'websiteUrl',
    ],
    hintCount: 0,
    ...overrides,
  };
}

export function makeCard(overrides: Partial<EventCard> = {}): EventCard {
  return {
    id: 'ev-1',
    title: 'Movienight',
    state: 'draft',
    publicStatus: 'scheduled',
    startsAt: '2026-11-05T18:00:00Z',
    endsAt: '2026-11-05T21:00:00Z',
    tzid: 'Europe/Berlin',
    allDay: false,
    organization: FSI,
    venueLabel: 'Kinosaal 9-133',
    primaryCategory: null,
    hasPoster: false,
    createdBy: { sub: 'u1', displayName: 'Mara Keller' },
    rev: 3,
    openQuestions: 0,
    formatSlug: null,
    howtoUnverified: false,
    ...overrides,
  };
}

export function fakeApi(overrides: Record<string, unknown> = {}) {
  return {
    listCards: jest.fn(() => of({ items: [makeCard()], total: 1, limit: 100, offset: 0 })),
    get: jest.fn(() => of(makeEvent())),
    create: jest.fn(() => of(makeEvent())),
    patch: jest.fn(() => of(makeEvent())),
    publish: jest.fn(() => of(makeEvent({ state: 'published' }))),
    unpublish: jest.fn(() => of(makeEvent())),
    archive: jest.fn(() => of(makeEvent({ state: 'archived' }))),
    restore: jest.fn(() => of(makeEvent())),
    cancel: jest.fn(() => of(makeEvent({ state: 'published', publicStatus: 'cancelled' }))),
    postpone: jest.fn(() => of(makeEvent({ state: 'published', publicStatus: 'postponed' }))),
    reinstate: jest.fn(() => of(makeEvent({ state: 'published' }))),
    revert: jest.fn(() => of(makeEvent())),
    hints: jest.fn(() => of({ items: [] })),
    draft: jest.fn(() => of(null)),
    saveDraft: jest.fn(() => of({ baseRev: 3, fields: {}, updatedAt: '2026-10-18T10:00:00Z' })),
    discardDraft: jest.fn(() => of(undefined)),
    revisions: jest.fn(() => of({ items: [], total: 0, limit: 50, offset: 0 })),
    revision: jest.fn(() => of({ rev: 3, snapshot: {} })),
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
