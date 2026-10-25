"""`POST /admin/venues/{id}/geocode` (gate `venue.manage`): look up one venue's address.

Nothing is stored on the venue; the editor takes the result over with a `PATCH`. A private
venue is refused before any network access. The answer is cached, so a repeat press costs no
request. The router commits (cache row and audit entry).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, Principal, require_principal
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.schemas import CamelModel
from app.modules.geocode import nominatim, service
from app.modules.taxonomy.models import Venue
from app.settings import Settings, get_settings
from app.shared.errors import NotFoundError, ProblemDetail, ValidationProblem
from app.shared.ssrf import Resolver, default_resolver

router = APIRouter(prefix="/admin/venues", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    422: _PROBLEM,
    429: _PROBLEM,
    503: _PROBLEM,
}
Manager = Annotated[Principal, Depends(require_principal("venue.manage"))]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class GeocodeOut(CamelModel):
    """The best match of a venue's address; `cached` tells that no request went out."""

    found: bool
    lat: Decimal | None
    lon: Decimal | None
    display_name: str | None
    cached: bool
    attribution: str = nominatim.ATTRIBUTION


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield the client for one geocode call."""
    async with nominatim.new_client() as client:
        yield client


def get_slot_redis(request: Request) -> Any:
    """Return the Redis client that holds the global slot (the arq pool), or `None`."""
    return getattr(request.app.state, "arq_pool", None)


def get_resolver() -> Resolver:
    """Return the DNS resolver of the SSRF check."""
    return default_resolver


@router.post("/{venue_id}/geocode", response_model=GeocodeOut, responses=_ERRORS)
async def geocode_venue(
    db: DbSession,
    principal: Manager,
    settings: SettingsDep,
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    redis: Annotated[Any, Depends(get_slot_redis)],
    resolver: Annotated[Resolver, Depends(get_resolver)],
    venue_id: UUID,
) -> GeocodeOut:
    """Look the address of a venue up at Nominatim (or in the cache) and return the match."""
    venue = await _venue(db, venue_id)
    query = service.address_query(venue.address, venue.postcode, venue.city)
    result = await service.resolve(db, redis, settings, query, client, resolver=resolver)
    await audit_record(
        db,
        actor=principal.sub,
        action=AuditAction.VENUE_GEOCODE,
        target_type="venue",
        target_id=str(venue.id),
        data={"found": result.found},
    )
    await db.commit()
    return GeocodeOut(
        found=result.found,
        lat=result.lat,
        lon=result.lon,
        display_name=result.display_name,
        cached=result.cached,
    )


async def _venue(db: AsyncSession, venue_id: UUID) -> Venue:
    venue = await db.get(Venue, venue_id)
    if venue is None:
        raise NotFoundError("venue not found")
    if venue.is_private:
        raise ValidationProblem("Private Orte werden nicht extern gesucht.", code="venue_private")
    return venue
