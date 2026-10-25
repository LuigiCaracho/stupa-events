"""Cached geocoding with the global 1 request per 2 seconds slot of the Nominatim policy.

`resolve` answers from `geocode_cache` when a row is still valid (hits 180 days, misses 30),
otherwise it claims the slot in Redis, asks Nominatim once and stores the answer, a miss
included. The slot is fail-closed: with no Redis the call is refused (503), because a lost
limit would break the usage policy. Private venues never reach this module (the callers
refuse them before any network access).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geocode import nominatim
from app.modules.geocode.models import GeocodeCache
from app.settings import Settings
from app.shared.errors import (
    FieldError,
    RateLimitedError,
    ServiceUnavailableError,
    ValidationProblem,
)
from app.shared.ssrf import Resolver, default_resolver
from app.shared.timeutil import utcnow

SLOT_KEY = "events:geocode:lock"
SLOT_MS = 2000
HIT_DAYS, MISS_DAYS = 180, 30
MAX_QUERY = 300
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    """What the admin sees: the best match, if any, and whether it came from the cache."""

    found: bool
    lat: Decimal | None
    lon: Decimal | None
    display_name: str | None
    cached: bool


def normalize(text: str) -> str:
    """Lower-case, trim and collapse white space."""
    return _SPACE.sub(" ", text).strip().lower()


def query_hash(norm: str) -> str:
    """Return the cache key of a normalized query."""
    return hashlib.sha256(norm.encode()).hexdigest()


def address_query(address: str | None, postcode: str | None, city: str | None) -> str:
    """Join street, postcode and town into one query.

    Raises:
        ValidationProblem: `address_incomplete` when the street or the town is missing.
    """
    if not (address and address.strip() and city and city.strip()):
        raise ValidationProblem(
            "Adresse und Ort sind nötig.",
            code="address_incomplete",
            errors=[FieldError(field="address", msg="address and city are required")],
        )
    return f"{address.strip()}, {' '.join(p for p in (postcode, city) if p).strip()}"


def _fresh(row: GeocodeCache, now: datetime) -> bool:
    return now - row.fetched_at < timedelta(days=HIT_DAYS if row.found else MISS_DAYS)


async def cached(db: AsyncSession, norm: str, now: datetime) -> GeocodeCache | None:
    """Return the cache row of a query while it is still valid."""
    row = await db.get(GeocodeCache, query_hash(norm))
    return row if row is not None and _fresh(row, now) else None


async def claim_slot(redis: Any) -> None:
    """Take the global slot or refuse.

    Raises:
        RateLimitedError: `geocode_rate`, another request used the slot less than 2 s ago.
        ServiceUnavailableError: `geocode_unavailable`, Redis is missing or fails.
    """
    if redis is None:
        raise ServiceUnavailableError(
            "Die Suche ist gerade nicht verfügbar.", code="geocode_unavailable"
        )
    try:
        taken = await redis.set(SLOT_KEY, "1", nx=True, px=SLOT_MS)
    except Exception as exc:  # noqa: BLE001 - any Redis failure closes the slot
        raise ServiceUnavailableError(
            "Die Suche ist gerade nicht verfügbar.", code="geocode_unavailable"
        ) from exc
    if not taken:
        raise RateLimitedError(
            "Bitte kurz warten.", retry_after=SLOT_MS // 1000, code="geocode_rate"
        )


async def _store(db: AsyncSession, norm: str, hit: nominatim.Hit | None, now: datetime) -> None:
    values: dict[str, Any] = {
        "query_hash": query_hash(norm),
        "query_norm": norm,
        "found": hit is not None,
        "lat": hit.lat if hit else None,
        "lon": hit.lon if hit else None,
        "display_name": hit.display_name if hit else None,
        "osm_type": hit.osm_type if hit else None,
        "osm_id": hit.osm_id if hit else None,
        "fetched_at": now,
    }
    statement = insert(GeocodeCache).values(**values)
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=["query_hash"],
            set_={k: v for k, v in values.items() if k != "query_hash"},
        )
    )


def _result(row: GeocodeCache, *, cached_: bool) -> GeocodeResult:
    return GeocodeResult(row.found, row.lat, row.lon, row.display_name, cached_)


async def resolve(
    db: AsyncSession,
    redis: Any,
    settings: Settings,
    text: str,
    client: httpx.AsyncClient,
    *,
    resolver: Resolver = default_resolver,
    now: datetime | None = None,
) -> GeocodeResult:
    """Look a query up in the cache, else once at Nominatim; the answer is cached either way.

    Raises:
        ServiceUnavailableError: `geocode_disabled`, `geocode_unavailable`.
        RateLimitedError: `geocode_rate`.
    """
    if not settings.nominatim_enabled:
        raise ServiceUnavailableError(
            "Die Ortssuche ist nicht eingeschaltet.", code="geocode_disabled"
        )
    moment = now or utcnow()
    norm = normalize(text)[:MAX_QUERY]
    if (row := await cached(db, norm, moment)) is not None:
        return _result(row, cached_=True)
    await claim_slot(redis)
    try:
        hit = await nominatim.search(client, settings, norm, resolver=resolver)
    except nominatim.NominatimError as exc:
        raise ServiceUnavailableError(
            "Die Ortssuche antwortet gerade nicht.", code="geocode_unavailable"
        ) from exc
    await _store(db, norm, hit, moment)
    if hit is None:
        return GeocodeResult(False, None, None, None, cached=False)
    return GeocodeResult(True, hit.lat, hit.lon, hit.display_name, cached=False)
