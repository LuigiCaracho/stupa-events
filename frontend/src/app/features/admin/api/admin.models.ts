/**
 * Wire models of the M2 admin endpoints (`/api/admin/*`, M2 contract 2.1); written by hand, camelCase.
 * The role lists below only drive the form selects; the server enforces which role fits which scope,
 * so a new role needs an edit here and in `app/shared/permissions.py`, never a rights decision.
 */
import type { OrgRef } from '../../dossiers/api/event.models';

export type CategoryKind = 'format' | 'fachschaft' | 'partner';
export type OrganizationKind =
  'stupa' | 'referat' | 'fachschaft' | 'partner' | 'hochschule' | 'redaktion';
export type RequiredProfile = 'generic' | 'party' | 'meeting' | 'trip';
export type ColorToken = 'orange' | 'blue' | 'petrol' | 'navy' | 'yellow' | 'red';
export type PublicPrecision = 'exact' | 'building' | 'hidden';
export type MappingRole =
  'admin' | 'editor' | 'stupa' | 'viewer' | 'submitter' | 'organizer';

export const CATEGORY_KINDS: readonly CategoryKind[] = ['format', 'fachschaft', 'partner'];
export const ORGANIZATION_KINDS: readonly OrganizationKind[] = [
  'stupa',
  'referat',
  'fachschaft',
  'partner',
  'hochschule',
  'redaktion',
];
export const REQUIRED_PROFILES: readonly RequiredProfile[] = [
  'generic',
  'party',
  'meeting',
  'trip',
];
export const COLOR_TOKENS: readonly ColorToken[] = [
  'orange',
  'blue',
  'petrol',
  'navy',
  'yellow',
  'red',
];
export const PUBLIC_PRECISIONS: readonly PublicPrecision[] = ['exact', 'building', 'hidden'];
export const GLOBAL_ROLES: readonly MappingRole[] = ['admin', 'editor', 'stupa'];
export const ORGANIZATION_ROLES: readonly MappingRole[] = ['viewer', 'submitter', 'organizer'];

export interface AdminCategory {
  id: string;
  slug: string;
  name: string;
  kind: CategoryKind;
  parentId: string | null;
  short: string | null;
  colorToken: ColorToken | null;
  description: string | null;
  requiredProfile: RequiredProfile;
  legacyWpId: number | null;
  sort: number;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export type CategoryWrite = Partial<
  Pick<
    AdminCategory,
    'name' | 'kind' | 'parentId' | 'short' | 'colorToken' | 'description' | 'requiredProfile' | 'sort' | 'active'
  >
> & { slug?: string };

export interface AdminOrganization {
  id: string;
  slug: string;
  name: string;
  kind: OrganizationKind;
  short: string;
  parentId: string | null;
  colorToken: ColorToken | null;
  categoryId: string | null;
  instagram: string[];
  legacyWpIds: number[];
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export type OrganizationWrite = Partial<
  Pick<
    AdminOrganization,
    'name' | 'kind' | 'short' | 'categoryId' | 'instagram' | 'active'
  >
> & { slug?: string };

export interface AdminVenue {
  id: string;
  slug: string;
  name: string;
  address: string | null;
  postcode: string | null;
  city: string | null;
  buildingNo: string | null;
  roomKey: string | null;
  campusBuildingNo: string | null;
  lat: number | null;
  lon: number | null;
  publicPrecision: PublicPrecision;
  isPrivate: boolean;
  geocodeSource: string | null;
  geocodedAt: string | null;
  legacyWpId: number | null;
  notes: string | null;
  active: boolean;
  createdAt: string;
  updatedAt: string;
}

export type VenueWrite = Partial<
  Pick<
    AdminVenue,
    | 'name'
    | 'address'
    | 'postcode'
    | 'city'
    | 'buildingNo'
    | 'roomKey'
    | 'publicPrecision'
    | 'isPrivate'
    | 'active'
  >
> & { slug?: string };

export interface GroupMapping {
  id: string;
  oidcGroup: string;
  role: MappingRole;
  organization: OrgRef | null;
  principalCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface MappingCreate {
  oidcGroup: string;
  role: MappingRole;
  organizationId?: string | null;
}

export interface MappingPatch {
  role?: MappingRole;
  organizationId?: string | null;
}

export interface AdminPrincipal {
  id: string;
  sub: string;
  displayName: string | null;
  email: string | null;
  groups: string[];
  lastLogin: string | null;
  active: boolean;
  sessionCount: number;
}

export interface RevokeResult {
  revoked: number;
}
