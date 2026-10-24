/**
 * Wire types of the public site API (B1 contract 2.2 to 2.7), camelCase as on the wire. All URLs are root-relative.
 * Kept in step with `backend/tests/schema/public-site-v1.json`.
 */

export type PublicStatus = 'scheduled' | 'cancelled' | 'postponed';

export interface PublicStatusReason {
  code: string;
  text: string;
}

export interface PublicOrganizationRef {
  slug: string;
  name: string;
  short: string;
}

export interface PublicCategoryRef {
  slug: string;
  name: string;
  kind: string;
}

export interface PublicImage {
  url: string;
  width: number;
  height: number;
  alt: string;
}

export interface PublicImageVariant {
  url: string;
  width: number;
  height: number;
}

export interface PublicImageSet {
  thumb: PublicImageVariant;
  card: PublicImageVariant;
  og: PublicImageVariant;
  alt: string;
  credit: string | null;
}

export interface PublicEventCard {
  slug: string;
  title: string;
  summary: string | null;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  /** Set for all-day events only; a timed event derives its Berlin days from `startsAt`/`endsAt`. */
  startsOn: string | null;
  endsOn: string | null;
  tzid: string;
  status: PublicStatus;
  statusReason: PublicStatusReason | null;
  organization: PublicOrganizationRef;
  venueName: string | null;
  categories: PublicCategoryRef[];
  image: PublicImage | null;
  path: string;
}

export interface PublicVenue {
  name: string;
  address: string | null;
  city: string | null;
}

export interface PublicFormatRef {
  slug: string;
  title: string;
}

export interface PublicEventDetail extends Omit<PublicEventCard, 'image'> {
  image: PublicImageSet | null;
  descriptionHtml: string | null;
  venue: PublicVenue | null;
  venueText: string | null;
  ticketUrl: string | null;
  websiteUrl: string | null;
  costText: string | null;
  format: PublicFormatRef | null;
  icsUrl: string;
  isPast: boolean;
  updatedAt: string;
  sequence: number;
  more: PublicEventCard[];
}

export interface CategoryFacet {
  slug: string;
  name: string;
  count: number;
}

export interface OrganizationFacet extends CategoryFacet {
  short: string;
}

export interface MonthFacet {
  month: string;
  count: number;
}

export interface PublicFacets {
  categories: CategoryFacet[];
  organizations: OrganizationFacet[];
  months: MonthFacet[];
}

export interface PublicSearchOut {
  items: PublicEventCard[];
  nextCursor: string | null;
  total: number | null;
  facets: PublicFacets | null;
}

export interface PublicTodayDay {
  date: string;
  items: PublicEventCard[];
}

export interface PublicTodayOut {
  generatedAt: string;
  date: string;
  today: PublicEventCard[];
  days: PublicTodayDay[];
  truncated?: boolean;
}

export interface PublicCategoryOut {
  slug: string;
  name: string;
  kind: string;
  parentSlug: string | null;
  description: string | null;
  upcomingCount: number;
}

export interface PublicCalendarEntry {
  slug: string;
  title: string;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  /** Set for all-day events only; a timed event derives its Berlin days from `startsAt`/`endsAt`. */
  startsOn: string | null;
  endsOn: string | null;
  status: PublicStatus;
  categorySlug: string | null;
}

export interface PublicCalendarDay {
  date: string;
  count: number;
  items: PublicCalendarEntry[];
}

export interface PublicCalendarOut {
  month: string;
  truncated: boolean;
  days: PublicCalendarDay[];
}

export interface PublicArchiveOut {
  years: number[];
  year: number | null;
  items: PublicEventCard[];
  nextCursor: string | null;
}

export interface PublicSearchQuery {
  q?: string;
  category?: readonly string[];
  organization?: readonly string[];
  from?: string;
  to?: string;
  past?: boolean;
  limit?: number;
  cursor?: string | null;
}
