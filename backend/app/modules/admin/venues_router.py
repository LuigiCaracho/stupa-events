"""Venue endpoints (`/admin/venues`, gate `venue.manage`). The router commits.

`lat` and `lon` come as a pair. A pair set by hand is a pin: the route records
`geocodeSource=pin` and the time. Clearing both clears both bookkeeping fields. A venue
is never deleted.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.deps import DbSession, Principal, require_principal
from app.modules.admin.patching import audit_config, changes, invalid, slug_taken
from app.modules.admin.schemas import AdminVenue, VenueCreate, VenuePatch
from app.modules.taxonomy.models import Venue
from app.modules.taxonomy.venues import normalize_room_key
from app.shared.errors import NotFoundError, ProblemDetail
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


def _bookkeeping(values: dict[str, Any]) -> dict[str, Any]:
    if "lat" not in values:
        return {}
    pinned = values["lat"] is not None
    return {
        "geocode_source": "pin" if pinned else None,
        "geocoded_at": utcnow() if pinned else None,
    }


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
async def patch_venue(db: DbSession, principal: Manager, venue_id: UUID, body: VenuePatch):
    """Change a venue (the slug never changes)."""
    venue = await db.get(Venue, venue_id)
    if venue is None:
        raise NotFoundError("venue not found")
    values = changes(body, _NULLABLE)
    _check_pair(values)
    for name, value in {**values, **_room(values), **_bookkeeping(values)}.items():
        setattr(venue, name, value)
    await db.flush()
    await db.refresh(venue)
    await audit_config(db, principal.sub, "venue", venue.id, list(values))
    await db.commit()
    return venue
