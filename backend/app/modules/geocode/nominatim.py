"""The Nominatim client: one guarded `GET /search` per call (usage policy of OSM).

The target passes `assert_allowed_url` with the single allowed host, redirects are off, the
timeout is short and the `User-Agent` names the application and a contact. The caller holds
the 1 request per 2 seconds slot; this module knows nothing about caching or limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.settings import Settings
from app.shared.ssrf import Resolver, SsrfError, assert_allowed_url, default_resolver

ALLOWED_HOSTS = ("nominatim.openstreetmap.org",)
TIMEOUT_SECONDS = 5.0
ATTRIBUTION = "© OpenStreetMap"


class NominatimError(Exception):
    """The upstream refused, timed out or answered something unreadable."""


@dataclass(frozen=True, slots=True)
class Hit:
    """The first result of a search."""

    lat: Decimal
    lon: Decimal
    display_name: str
    osm_type: str | None
    osm_id: int | None


def user_agent(settings: Settings) -> str:
    """Build the `User-Agent` the policy asks for: application, version and contact."""
    return (
        f"STUPA-Events/{settings.app_version} "
        f"(+{settings.public_base_url}; {settings.nominatim_contact})"
    )


def new_client() -> httpx.AsyncClient:
    """Return a client without redirects and with the short timeout."""
    return httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT_SECONDS)


def _hit(item: dict[str, object]) -> Hit:
    osm_id = item.get("osm_id")
    osm_type = item.get("osm_type")
    return Hit(
        lat=Decimal(str(item["lat"])).quantize(Decimal("0.000001")),
        lon=Decimal(str(item["lon"])).quantize(Decimal("0.000001")),
        display_name=str(item.get("display_name", ""))[:300],
        osm_type=osm_type if isinstance(osm_type, str) else None,
        osm_id=osm_id if isinstance(osm_id, int) else None,
    )


async def search(
    client: httpx.AsyncClient,
    settings: Settings,
    query: str,
    *,
    resolver: Resolver = default_resolver,
) -> Hit | None:
    """Ask Nominatim for one result; `None` means the place is unknown.

    Raises:
        NominatimError: The host is not allowed, the call failed or the answer is malformed.
    """
    url = f"{settings.nominatim_base_url.rstrip('/')}/search"
    try:
        assert_allowed_url(url, allowlist=ALLOWED_HOSTS, resolver=resolver)
    except SsrfError as exc:
        raise NominatimError(str(exc)) from exc
    try:
        response = await client.get(
            url,
            params={"q": query, "format": "jsonv2", "limit": "1"},
            headers={"User-Agent": user_agent(settings), "Accept": "application/json"},
        )
        response.raise_for_status()
        items = response.json()
        return _hit(items[0]) if items else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        raise NominatimError(type(exc).__name__) from exc
