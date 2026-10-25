"""Fixtures of the geocode tests: a mock Nominatim, a fake slot and a clean venue table."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text

from app.modules.geocode.router import get_http_client, get_resolver, get_slot_redis
from app.modules.taxonomy.venue_reference import VENUES
from app.settings import get_settings
from tests._support.factories import make_settings
from tests.integration.events.harness import Api, api, clean_events, db_roles  # noqa: F401

HIT = [
    {
        "lat": "48.4826171",
        "lon": "9.1874312",
        "display_name": "Gebäude 9, Alteburgstraße, Reutlingen",
        "osm_type": "way",
        "osm_id": 290446675,
    }
]


class Slot:
    """Stands in for Redis: `SET NX PX` succeeds once until `expire` is called."""

    def __init__(self) -> None:
        self.taken = False
        self.broken = False
        self.extended = 0

    async def set(
        self, key: str, value: str, nx: bool = False, px: int | None = None
    ) -> bool | None:
        if self.broken:
            raise ConnectionError("redis is gone")
        if nx and self.taken:
            return None
        self.taken = True
        return True

    async def pexpire(self, key: str, px: int) -> bool:
        self.extended += 1
        return True

    def expire(self) -> None:
        self.taken = False


@dataclass
class Upstream:
    """The mock Nominatim: records requests and answers with `body` or `status`."""

    body: Any = field(default_factory=lambda: HIT)
    status: int = 200
    requests: list[httpx.Request] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


@dataclass
class Rig:
    """What a geocode test steers."""

    api: Api
    upstream: Upstream
    slot: Slot
    configure: Callable[..., None]


@pytest.fixture
def rig(api: Api) -> Iterator[Rig]:  # noqa: F811
    upstream, slot = Upstream(), Slot()

    async def client() -> Any:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(upstream.handler), follow_redirects=False
        ) as mock:
            yield mock

    def configure(**over: Any) -> None:
        values = {"nominatim_enabled": True, "nominatim_contact": "kontakt@example.org", **over}
        api.app.dependency_overrides[get_settings] = lambda: make_settings(**values)

    overrides = api.app.dependency_overrides
    overrides[get_http_client] = client
    overrides[get_slot_redis] = lambda: slot
    overrides[get_resolver] = lambda: lambda host: ["93.184.216.34"]
    configure()
    yield Rig(api, upstream, slot, configure)
    for dependency in (get_http_client, get_slot_redis, get_resolver, get_settings):
        overrides.pop(dependency, None)


@pytest.fixture(autouse=True)
def reference_state(engine: Engine) -> Iterator[None]:
    """Remove the venues and cache rows a test added."""
    yield
    ids = [str(row["id"]) for row in VENUES]
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        conn.execute(text("DELETE FROM venue WHERE id::text <> ALL(:ids)"), {"ids": ids})
        conn.execute(text("DELETE FROM geocode_cache"))
        conn.execute(
            text(
                "UPDATE venue SET lat = NULL, lon = NULL, geocode_source = NULL, geocoded_at = NULL, "
                "public_precision = 'hidden', is_private = false"
            )
        )
