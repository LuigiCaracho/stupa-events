/** Wire models of the library (M5 contract 5), camelCase, written by hand. */
import type { Facet } from '../../archive/model/archive.models';

export type LibraryKind = 'document' | 'attachment';

export interface LibrarySource {
  type: 'event' | 'format';
  id: string;
  title: string;
  startsAt: string | null;
  organization: { slug: string; short: string };
  own: boolean;
}

export interface LibraryItem {
  kind: LibraryKind;
  id: string;
  title: string;
  subKind: string;
  source: LibrarySource;
  categories: { slug: string; name: string }[];
  year: number | null;
  verifiedAt: string | null;
  updatedAt: string;
  mime?: string;
  sizeBytes?: number;
}

export interface LibraryFacets {
  category: Facet[];
  organization: Facet[];
  year: Facet[];
  kind: Facet[];
}

export interface LibraryPage {
  items: LibraryItem[];
  total: number;
  limit: number;
  offset: number;
  facets: LibraryFacets;
}

export interface LibraryQuery {
  q?: string;
  kind?: string;
  category?: string;
  organization?: string;
  year?: string;
  format?: string;
  limit?: number;
  offset?: number;
}
