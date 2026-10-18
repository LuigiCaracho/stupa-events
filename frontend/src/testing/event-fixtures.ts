/** Test fixtures of the dossier specs: a complete event DTO and a fake `EventsApi`. */
import { of } from 'rxjs';
import type { MeOrganization } from '../app/core/api/models';
import type { EventDto, GuardResult, OrgRef } from '../app/features/dossiers/api/event.models';

export const FSI: OrgRef = { id: 'org-fsi', slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' };

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

export function makeGuards(overrides: Partial<GuardResult> = {}): GuardResult {
  return { transition: 'T02', allowed: true, reasons: [], ...overrides };
}

export function fakeApi(overrides: Record<string, unknown> = {}) {
  return {
    list: jest.fn(() => of({ items: [makeEvent()], total: 1, limit: 200, offset: 0 })),
    get: jest.fn(() => of(makeEvent())),
    create: jest.fn(() => of(makeEvent({ state: 'idea' }))),
    patch: jest.fn(() => of(makeEvent())),
    transition: jest.fn(() => of(makeEvent({ state: 'in_review' }))),
    guards: jest.fn(() => of(makeGuards())),
    uploadPoster: jest.fn(() => of({})),
    imageException: jest.fn(() => of(makeEvent())),
    posterUrl: jest.fn((id: string) => `/api/events/${id}/poster/file?variant=thumb400`),
    organizations: jest.fn(() => of([FSI])),
    categories: jest.fn(() => of([{ id: 'cat-1', slug: 'kino', name: 'Kino', kind: 'format' }])),
    ...overrides,
  };
}

export function fakeAuth(overrides: Record<string, unknown> = {}) {
  return {
    organizations: () => [{ slug: 'fsi', role: 'organizer' }],
    can: () => false,
    ...overrides,
  };
}
