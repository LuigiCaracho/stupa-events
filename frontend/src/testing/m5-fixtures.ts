/** Test fixtures of the M5 specs: search hits, templates, formats, library items, the calendar and the result of an edition. */
import type {
  ClonePreview,
  LastTime,
  SearchHit,
  SearchOut,
  TemplateCard,
} from '../app/features/archive/model/archive.models';
import type { CalendarEntry } from '../app/features/calendar/model/calendar.models';
import type { FormatOut } from '../app/features/formats/model/format.models';
import type { LibraryItem } from '../app/features/library/model/library.models';

export function makeHit(over: Partial<SearchHit> = {}): SearchHit {
  return {
    kind: 'event',
    id: 'ev-9',
    title: 'Fachschaftssitzung WS25/26',
    subtitle: 'FSI · 12.11.2025',
    state: 'archived',
    startsAt: '2025-11-12T17:00:00Z',
    organization: { slug: 'fsi', short: 'FSI' },
    format: null,
    howtoVerifiedAt: null,
    howtoUnverified: false,
    foreign: false,
    link: '/dossiers/ev-9',
    rank: 1,
    highlights: [],
    ...over,
  };
}

export function makeSearch(over: Partial<SearchOut> = {}): SearchOut {
  return {
    q: 'sitzung',
    scope: 'events',
    total: 1,
    hits: [makeHit()],
    facets: {
      state: [{ value: 'archived', label: 'Archiv', count: 1 }],
      organization: [{ value: 'fsi', label: 'FSI', count: 1 }],
      year: [{ value: '2025', label: '2025', count: 1 }],
      category: [],
      format: [],
    },
    suggestion: null,
    ...over,
  };
}

export function makeTemplate(over: Partial<TemplateCard> = {}): TemplateCard {
  return {
    id: 'tpl-1',
    title: 'STUPA Movienight: Whiplash (OmU)',
    startsAt: '2026-06-02T17:00:00Z',
    allDay: false,
    state: 'archived',
    organization: { slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
    format: { slug: 'movienight', title: 'Movienight' },
    categories: [{ slug: 'kino', name: 'Kino' }],
    attendance: 87,
    howtoVerifiedAt: '2026-02-12T10:00:00Z',
    howtoUnverified: false,
    hasHowto: true,
    foreign: false,
    sharedDocuments: 1,
    checklistItems: 6,
    ...over,
  };
}

export function makeLastTime(over: Partial<LastTime> = {}): LastTime {
  return {
    source: {
      id: 'tpl-1',
      title: 'Movienight SoSe26',
      startsAt: '2026-06-02T17:00:00Z',
      state: 'archived',
      organization: { slug: 'fsi', short: 'FSI' },
      own: true,
    },
    attendance: 87,
    costsCents: 24500,
    revenueCents: 13000,
    notes: null,
    retrospective: null,
    restricted: false,
    ...over,
  };
}

export function makePreview(over: Partial<ClonePreview> = {}): ClonePreview {
  return {
    report: [
      { part: 'title', mode: 'copy', reason: 'clone.reason.title' },
      { part: 'checklist', mode: 'partial', reason: 'clone.reason.checklist', count: 6 },
      { part: 'venueText', mode: 'reset', reason: 'clone.reason.location' },
      { part: 'shared', mode: 'link', reason: 'clone.reason.shared' },
      { part: 'poster', mode: 'never', reason: 'clone.reason.poster' },
    ],
    lastTime: makeLastTime(),
    ...over,
  };
}

export function makeFormat(over: Partial<FormatOut> = {}): FormatOut {
  return {
    slug: 'movienight',
    title: 'Movienight',
    organization: { slug: 'fsi', short: 'FSI', name: 'Fachschaft Informatik' },
    active: true,
    lastVerifiedBy: 'Mara Keller',
    lastVerifiedAt: '2026-02-12T10:00:00Z',
    howtoStale: false,
    lastEdition: { id: 'ed-2', title: 'Movienight SoSe26', startsAt: '2026-06-02T17:00:00Z' },
    defaults: {},
    descriptionMd: 'Kino im Hörsaal.',
    masterHowto: {
      id: 'doc-1',
      rev: 2,
      title: 'Movienight Anleitung',
      verifiedAt: '2026-02-12T10:00:00Z',
      verifiedBy: 'Mara Keller',
      bodyMd: '## Vorher',
    },
    checklist: {
      profile: 'generic',
      template: { slug: 'generic', name: 'Standard' },
      items: [{ text: 'Raum buchen', phase: 'planning', required: true, dueOffsetDays: -14 }],
    },
    mailTemplates: [{ id: 'mt-1', title: 'Einladung', eventId: 'ed-2' }],
    editions: [
      {
        id: 'ed-1',
        title: 'Movienight WS25/26',
        startsAt: '2025-11-12T17:00:00Z',
        state: 'archived',
        attendance: 60,
        costsCents: 20000,
        howtoUnverified: false,
        foreign: false,
      },
      {
        id: 'ed-2',
        title: 'Movienight SoSe26',
        startsAt: '2026-06-02T17:00:00Z',
        state: 'archived',
        attendance: 87,
        costsCents: 24500,
        howtoUnverified: true,
        foreign: false,
      },
    ],
    ...over,
  } as FormatOut;
}

export function makeLibraryItem(over: Partial<LibraryItem> = {}): LibraryItem {
  return {
    kind: 'document',
    id: 'doc-7',
    title: 'Anleitung Hüttencafé',
    subKind: 'howto',
    source: {
      type: 'event',
      id: 'ev-3',
      title: 'Hüttencafé 2025',
      startsAt: '2025-12-01T10:00:00Z',
      organization: { slug: 'makers', short: 'MAKERS' },
      own: false,
    },
    categories: [{ slug: 'cafe', name: 'Café' }],
    year: 2025,
    verifiedAt: null,
    updatedAt: '2026-01-01T10:00:00Z',
    ...over,
  };
}

export function makeCalendarEntry(over: Partial<CalendarEntry> = {}): CalendarEntry {
  return {
    id: 'ev-1',
    title: 'Movienight',
    startsAt: '2026-10-20T17:00:00Z',
    endsAt: '2026-10-20T19:00:00Z',
    allDay: false,
    startsOn: '2026-10-20',
    endsOn: '2026-10-20',
    state: 'published',
    publicStatus: 'scheduled',
    organization: { slug: 'fsi', short: 'FSI', colorToken: 'petrol' },
    category: null,
    venueName: null,
    howtoUnverified: false,
    ...over,
  };
}
