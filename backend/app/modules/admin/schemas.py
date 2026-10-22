"""Schemas of the admin API: taxonomy, group mappings and principals (camelCase, `extra=forbid`).

Slugs are immutable, so no patch schema has a `slug` field and the `extra=forbid` rule
turns an attempt into a 422. Colour tokens and kinds are literals; a hex value is never
accepted.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints

from app.modules.auth.schemas import CamelModel
from app.modules.orgs.schemas import OrgRef

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,59}$"
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_INSTAGRAM = re.compile(r"^[A-Za-z0-9._]{1,30}$")

Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]
ColorToken = Literal["orange", "blue", "petrol", "navy", "yellow", "red"]
OrganizationKind = Literal["stupa", "referat", "fachschaft", "partner", "hochschule", "redaktion"]
CategoryKind = Literal["format", "fachschaft", "partner"]
RequiredProfile = Literal["generic", "party", "meeting", "trip"]
PublicPrecision = Literal["exact", "building", "hidden"]
MappingRole = Literal["admin", "editor", "stupa", "member", "viewer", "submitter", "organizer"]


def _clean(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("control characters are not allowed")
    return value.strip()


def _clean_optional(value: str | None) -> str | None:
    return None if value is None else (_clean(value) or None)


def _instagram(values: list[str]) -> list[str]:
    handles = [value.strip().lstrip("@") for value in values]
    if not all(_INSTAGRAM.fullmatch(handle) for handle in handles):
        raise ValueError("invalid Instagram handle")
    return handles


Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_clean),
]
OptText = Annotated[str | None, Field(max_length=200), AfterValidator(_clean_optional)]
Description = Annotated[str | None, Field(max_length=300), AfterValidator(_clean_optional)]
Notes = Annotated[str | None, Field(max_length=2000), AfterValidator(_clean_optional)]
Handles = Annotated[list[str], Field(max_length=10), AfterValidator(_instagram)]
Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)]


class AdminOrganization(CamelModel):
    """An organization with its flags, inactive ones included."""

    id: UUID
    slug: str
    name: str
    kind: OrganizationKind
    short: str
    parent_id: UUID | None
    color_token: ColorToken | None
    category_id: UUID | None
    instagram: list[str]
    legacy_wp_ids: list[int]
    active: bool
    created_at: datetime
    updated_at: datetime


class OrganizationCreate(CamelModel):
    """Body of `POST /admin/organizations`."""

    slug: Slug
    name: Text
    kind: OrganizationKind
    short: Text
    parent_id: UUID | None = None
    color_token: ColorToken | None = None
    category_id: UUID | None = None
    instagram: Handles = Field(default_factory=list)
    active: bool = True


class OrganizationPatch(CamelModel):
    """Body of `PATCH /admin/organizations/{id}`; absent fields stay as they are."""

    name: Text | None = None
    kind: OrganizationKind | None = None
    short: Text | None = None
    parent_id: UUID | None = None
    color_token: ColorToken | None = None
    category_id: UUID | None = None
    instagram: Handles | None = None
    active: bool | None = None


class AdminCategory(CamelModel):
    """A category with its flags, inactive ones included."""

    id: UUID
    slug: str
    name: str
    kind: CategoryKind
    parent_id: UUID | None
    short: str | None
    color_token: ColorToken | None
    required_profile: RequiredProfile
    legacy_wp_id: int | None
    sort: int
    active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime


class CategoryCreate(CamelModel):
    """Body of `POST /admin/categories`."""

    slug: Slug
    name: Text
    kind: CategoryKind
    parent_id: UUID | None = None
    short: OptText = None
    color_token: ColorToken | None = None
    required_profile: RequiredProfile = "generic"
    sort: int = Field(default=0, ge=0, le=10000)
    active: bool = True
    description: Description = None


class CategoryPatch(CamelModel):
    """Body of `PATCH /admin/categories/{id}`."""

    name: Text | None = None
    kind: CategoryKind | None = None
    parent_id: UUID | None = None
    short: OptText = None
    color_token: ColorToken | None = None
    required_profile: RequiredProfile | None = None
    sort: int | None = Field(default=None, ge=0, le=10000)
    active: bool | None = None
    description: Description = None


class AdminVenue(CamelModel):
    """A venue with all columns, inactive ones included."""

    id: UUID
    slug: str
    name: str
    address: str | None
    postcode: str | None
    city: str | None
    building_no: str | None
    room_key: str | None
    campus_building_no: str | None
    lat: Decimal | None
    lon: Decimal | None
    public_precision: PublicPrecision
    is_private: bool
    geocode_source: Literal["pin", "nominatim", "import"] | None
    geocoded_at: datetime | None
    legacy_wp_id: int | None
    notes: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class VenueCreate(CamelModel):
    """Body of `POST /admin/venues`."""

    slug: Slug
    name: Text
    address: OptText = None
    postcode: OptText = None
    city: OptText = None
    building_no: OptText = None
    room_key: OptText = None
    campus_building_no: OptText = None
    lat: Latitude | None = None
    lon: Longitude | None = None
    public_precision: PublicPrecision = "hidden"
    is_private: bool = False
    notes: Notes = None
    active: bool = True


class VenuePatch(CamelModel):
    """Body of `PATCH /admin/venues/{id}`."""

    name: Text | None = None
    address: OptText = None
    postcode: OptText = None
    city: OptText = None
    building_no: OptText = None
    room_key: OptText = None
    campus_building_no: OptText = None
    lat: Latitude | None = None
    lon: Longitude | None = None
    public_precision: PublicPrecision | None = None
    is_private: bool | None = None
    notes: Notes = None
    active: bool | None = None


class GroupMappingOut(CamelModel):
    """A group mapping with the number of people whose cached groups contain the group."""

    id: UUID
    oidc_group: str
    role: MappingRole
    organization: OrgRef | None
    principal_count: int
    created_at: datetime
    updated_at: datetime


class GroupMappingCreate(CamelModel):
    """Body of `POST /admin/group-mappings`."""

    oidc_group: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
        AfterValidator(_clean),
    ]
    role: MappingRole
    organization_id: UUID | None = None


class GroupMappingPatch(CamelModel):
    """Body of `PATCH /admin/group-mappings/{id}`; `oidcGroup` cannot change."""

    role: MappingRole | None = None
    organization_id: UUID | None = None


class AdminPrincipal(CamelModel):
    """A person as the admin sees them (the group cache and the open sessions)."""

    id: UUID
    sub: str
    display_name: str | None
    email: str | None
    groups: list[str]
    last_login: datetime | None
    active: bool
    session_count: int
