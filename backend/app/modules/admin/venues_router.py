"""Venue endpoints (`/admin/venues`, gate `venue.manage`). The router commits.

`lat` and `lon` come as a pair. A pair set by hand is a pin: the route records
`geocodeSource=pin` and the time. A body may ask for `nominatim` instead; the route grants it
only when the pair equals the cached answer for the venue's current address, and never for a
private venue. Clearing both clears both bookkeeping fields. A precision of `exact` or
`building` needs a coordinate or a building number. A venue is never deleted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, Principal, require_principal
from app.modules.admin.patching import audit_config, changes, invalid, invalidate_feed, slug_taken
from app.modules.admin.schemas import AdminVenue, VenueCreate, VenuePatch
from app.modules.geocode import service as geocoding
from app.modules.taxonomy.models import Venue
from app.modules.taxonomy.venues import normalize_room_key
from app.shared.errors import NotFoundError, ProblemDetail, ValidationProblem
from app.shared.timeutil import utcnow

router = APIRouter(prefix="/admin/venues", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
}
Manager = Annotated[Principal, Depends(require_principal("venue.manage"))]
_GEO = frozenset({"public_precision", "lat", "building_no"})
_NULLABLE = frozenset(
    {
        "address",
        "postcode",
        "city",
        "building_no",
        "room_key",
        "campus_building_no",
        "lat",
        "lon",
        "notes",
    }
)


def _check_pair(values: dict[str, Any]) -> None:
    """Refuse a body that names one coordinate, or that mixes a value with `null`."""
    named = {"lat", "lon"} & values.keys()
    if not named:
        return
    if named != {"lat", "lon"} or (values["lat"] is None) != (values["lon"] is None):
        raise invalid("lat", "lat and lon go together", "coordinates_incomplete")


def _bookkeeping(values: dict[str, Any], source: str = "pin") -> dict[str, Any]:
    if "lat" not in values:
        return {}
    pinned = values["lat"] is not None
    return {
        "geocode_source": source if pinned else None,
        "geocoded_at": utcnow() if pinned else None,
    }


def _close(a: Decimal, b: Decimal | None) -> bool:
    return b is not None and abs(a - b) <= Decimal("0.000001")


async def _source(db: AsyncSession, venue: Venue, values: dict[str, Any]) -> str:
    """Grant `nominatim` only for a public venue whose pair equals the cached answer."""
    if values.get("geocode_source") != "nominatim" or values.get("lat") is None:
        return "pin"
    if values.get("is_private", venue.is_private):
        return "pin"
    address = {k: values.get(k, getattr(venue, k)) for k in ("address", "postcode", "city")}
    try:
        norm = geocoding.normalize(geocoding.address_query(**address))
    except ValidationProblem:
        return "pin"
    row = await geocoding.cached(db, norm, utcnow())
    if row is None or not row.found:
        return "pin"
    same = _close(values["lat"], row.lat) and _close(values["lon"], row.lon)
    return "nominatim" if same else "pin"


def _check_precision(current: dict[str, Any], values: dict[str, Any]) -> None:
    """Refuse a public precision that has nothing to show."""
    if not _GEO & values.keys():
        return
    merged = {**current, **values}
    if (
        merged.get("public_precision", "hidden") != "hidden"
        and merged.get("lat") is None
        and not merged.get("building_no")
    ):
        raise invalid("publicPrecision", "needs a coordinate or a building", "coordinates_missing")


def _room(values: dict[str, Any]) -> dict[str, Any]:
    room = values.get("room_key")
    return {"room_key": normalize_room_key(room) or room} if room else {}


@router.get("", response_model=list[AdminVenue], responses=_ERRORS)
async def list_venues(db: DbSession, _: Manager):
    """List all venues, inactive ones included."""
    return list(await db.scalars(select(Venue).order_by(Venue.name)))


@router.post("", response_model=AdminVenue, status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_venue(db: DbSession, principal: Manager, body: VenueCreate):
    """Create a venue."""
    values = body.model_dump()
    _check_pair({k: values[k] for k in ("lat", "lon")})
    _check_precision({}, values)
    if await db.scalar(select(Venue.id).where(Venue.slug == body.slug)):
        raise slug_taken()
    venue = Venue(**{**values, **_room(values), **_bookkeeping(values)})
    db.add(venue)
    await db.flush()
    await db.refresh(venue)
    await audit_config(db, principal.sub, "venue", venue.id, ["slug", *body.model_fields_set])
    await db.commit()
    return venue


@router.patch("/{venue_id}", response_model=AdminVenue, responses=_ERRORS)
async def patch_venue(
    request: Request, db: DbSession, principal: Manager, venue_id: UUID, body: VenuePatch
):
    """Change a venue (the slug never changes)."""
    venue = await db.get(Venue, venue_id)
    if venue is None:
        raise NotFoundError("venue not found")
    values = changes(body, _NULLABLE | {"geocode_source"})
    _check_pair(values)
    _check_precision({name: getattr(venue, name) for name in _GEO}, values)
    source = await _source(db, venue, values)
    values.pop("geocode_source", None)
    for name, value in {**values, **_room(values), **_bookkeeping(values, source)}.items():
        setattr(venue, name, value)
    await db.flush()
    await db.refresh(venue)
    await audit_config(db, principal.sub, "venue", venue.id, list(values))
    await db.commit()
    await invalidate_feed(request)
    return venue
