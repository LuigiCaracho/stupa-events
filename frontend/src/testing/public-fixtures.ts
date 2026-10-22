/** Builders for the public API answers used by the specs of the public pages. */
import type {
  PublicCategoryOut,
  PublicEventCard,
  PublicEventDetail,
  PublicSearchOut,
} from '../app/features/public/model/public.models';

export function card(over: Partial<PublicEventCard> = {}): PublicEventCard {
  return {
    slug: 'movienight',
    title: 'Movienight: Arrival',
    summary: 'Ein Film.',
    startsAt: '2026-10-22T18:00:00Z',
    endsAt: '2026-10-22T20:00:00Z',
    allDay: false,
    startsOn: '2026-10-22',
    endsOn: '2026-10-22',
    tzid: 'Europe/Berlin',
    status: 'scheduled',
    statusReason: null,
    organization: { slug: 'stupa', name: 'Studierendenparlament', short: 'STUPA' },
    venueName: 'Kinosaal',
    categories: [{ slug: 'kultur', name: 'Kultur', kind: 'topic' }],
    image: { url: '/api/public/media/a.webp', width: 400, height: 210, alt: 'Plakat' },
    path: '/e/movienight',
    ...over,
  };
}

export function detail(over: Partial<PublicEventDetail> = {}): PublicEventDetail {
  const base = { ...card(), image: undefined };
  return {
    ...base,
    image: {
      thumb: { url: '/api/public/media/a.webp', width: 400, height: 210 },
      card: { url: '/api/public/media/a-c.webp', width: 1200, height: 630 },
      og: { url: '/api/public/media/a-o.webp', width: 1200, height: 630 },
      alt: 'Plakat',
      credit: 'Foto: Beispiel',
    },
    descriptionHtml: '<p>Der <strong>lange</strong> Text.</p>',
    venue: { name: 'Kinosaal 9-133', address: 'Alteburgstraße 150', city: 'Reutlingen' },
    venueText: null,
    ticketUrl: 'https://tickets.example/x',
    websiteUrl: null,
    costText: 'Eintritt frei',
    format: null,
    icsUrl: '/ics/e/movienight.ics',
    isPast: false,
    updatedAt: '2026-10-01T10:00:00Z',
    sequence: 0,
    more: [],
    ...over,
  };
}

export function search(
  items: PublicEventCard[],
  over: Partial<PublicSearchOut> = {},
): PublicSearchOut {
  return {
    items,
    nextCursor: null,
    total: items.length,
    facets: {
      categories: [{ slug: 'kultur', name: 'Kultur', count: items.length }],
      organizations: [
        { slug: 'stupa', name: 'Studierendenparlament', short: 'STUPA', count: items.length },
      ],
      months: [],
    },
    ...over,
  };
}

export const CATEGORIES: PublicCategoryOut[] = [
  {
    slug: 'kultur',
    name: 'Kultur',
    kind: 'topic',
    parentSlug: null,
    description: 'Kino und mehr.',
    upcomingCount: 3,
  },
  {
    slug: 'party',
    name: 'Party',
    kind: 'topic',
    parentSlug: 'kultur',
    description: null,
    upcomingCount: 0,
  },
];
