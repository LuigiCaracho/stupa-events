/** Test fixtures of the admin specs: complete admin DTOs with overrides, and a typed jest fake per API service. */
import type {
  AdminCategory,
  AdminOrganization,
  AdminPrincipal,
  AdminVenue,
  GroupMapping,
} from '../app/features/admin/api/admin.models';

const STAMP = '2026-10-01T10:00:00Z';

export const makeCategory = (o: Partial<AdminCategory> = {}): AdminCategory => ({
  id: 'cat-1',
  slug: 'kino',
  name: 'Kino',
  kind: 'format',
  parentId: null,
  short: null,
  colorToken: null,
  description: null,
  requiredProfile: 'generic',
  legacyWpId: null,
  sort: 0,
  active: true,
  createdAt: STAMP,
  updatedAt: STAMP,
  ...o,
});

export const makeVenue = (o: Partial<AdminVenue> = {}): AdminVenue => ({
  id: 'ven-1',
  slug: 'kinosaal',
  name: 'Kinosaal',
  address: null,
  postcode: null,
  city: null,
  buildingNo: '9',
  roomKey: '133',
  campusBuildingNo: null,
  lat: null,
  lon: null,
  publicPrecision: 'building',
  isPrivate: false,
  geocodeSource: null,
  geocodedAt: null,
  legacyWpId: null,
  notes: null,
  active: true,
  createdAt: STAMP,
  updatedAt: STAMP,
  ...o,
});

export const makeOrganization = (o: Partial<AdminOrganization> = {}): AdminOrganization => ({
  id: 'org-fsi',
  slug: 'fsi',
  name: 'Fachschaft Informatik',
  kind: 'fachschaft',
  short: 'FSI',
  parentId: null,
  colorToken: null,
  categoryId: null,
  instagram: ['fsi_rt'],
  legacyWpIds: [],
  active: true,
  createdAt: STAMP,
  updatedAt: STAMP,
  ...o,
});

export const makeMapping = (o: Partial<GroupMapping> = {}): GroupMapping => ({
  id: 'map-1',
  oidcGroup: 'events-fsi-organizer',
  role: 'organizer',
  organization: { id: 'org-fsi', slug: 'fsi', name: 'Fachschaft Informatik', short: 'FSI' },
  principalCount: 2,
  createdAt: STAMP,
  updatedAt: STAMP,
  ...o,
});

export const makePrincipal = (o: Partial<AdminPrincipal> = {}): AdminPrincipal => ({
  id: 'p-1',
  sub: 'sub-1',
  displayName: 'Mia Muster',
  email: 'mia@example.test',
  groups: ['events-fsi-organizer'],
  lastLogin: '2026-10-17T09:30:00Z',
  active: true,
  sessionCount: 2,
  ...o,
});
