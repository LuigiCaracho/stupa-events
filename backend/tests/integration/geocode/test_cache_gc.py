"""`gc_geocode_cache` drops hits older than 180 days and misses older than 30 days."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api
from tests.integration.geocode.conftest import Rig  # noqa: F401
from worker.geocode_gc import gc_geocode_cache

pytestmark = pytest.mark.integration


async def test_expired_rows_go_and_fresh_ones_stay(api: Api) -> None:
    rows = (
        ("old-hit", True, 181),
        ("new-hit", True, 179),
        ("old-miss", False, 31),
        ("new-miss", False, 29),
    )
    for key, found, days in rows:
        await api.sql(
            "INSERT INTO geocode_cache (query_hash, query_norm, found, lat, lon, fetched_at) VALUES "
            "(:h, :h, :f, CASE WHEN :f THEN 48.4 END, CASE WHEN :f THEN 9.1 END, "
            "now() - make_interval(days => :d))",
            h=key,
            f=found,
            d=days,
        )
    line = await gc_geocode_cache({"gc_sessionmaker": api.maker})
    assert line == "gc_geocode_cache: deleted=2"
    left = {r[0] for r in await api.sql("SELECT query_hash FROM geocode_cache")}
    assert left == {"new-hit", "new-miss"}
