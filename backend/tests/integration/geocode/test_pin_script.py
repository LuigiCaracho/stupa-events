"""`scripts.pin_venues`: dry run writes nothing, apply pins the campus, live asks Nominatim politely."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.modules.taxonomy.models import CampusBuilding, Venue
from app.modules.taxonomy.pinning import plan
from app.settings import get_settings
from scripts import pin_venues
from tests.integration.geocode.conftest import Rig

pytestmark = pytest.mark.integration


async def run(rig: Rig, *, apply: bool, live: bool = False, private: str | None = None) -> dict:
    async with rig.api.maker() as session:
        if private:
            await session.execute(
                Venue.__table__.update().where(Venue.slug == private).values(is_private=True)
            )
        venues = list(await session.scalars(select(Venue).order_by(Venue.name)))
        polygons = {b.number: b.geometry for b in await session.scalars(select(CampusBuilding))}
        by_slug = {v.slug: v for v in venues}
        client = (
            httpx.AsyncClient(transport=httpx.MockTransport(rig.upstream.handler)) if live else None
        )
        cfg = rig.api.app.dependency_overrides[get_settings]()
        outcomes = {
            d.slug: await pin_venues.run_one(
                session,
                rig.slot if live else None,
                client,
                cfg,
                d,
                by_slug[d.slug],
                apply=apply,
            )
            for d in plan(venues, polygons)
        }
        if apply:
            await session.commit()
        if client:
            await client.aclose()
    return outcomes


async def pinned(rig: Rig) -> dict[str, tuple]:
    rows = await rig.api.sql(
        "SELECT slug, lat, lon, geocode_source, public_precision FROM venue WHERE lat IS NOT NULL"
    )
    return {r[0]: tuple(r[1:]) for r in rows}


async def test_the_dry_run_writes_nothing(rig: Rig) -> None:
    outcomes = await run(rig, apply=False)
    assert outcomes["kinosaal-9-133"][1] == "würde gepinnt"
    assert outcomes["davos"][1].startswith("offen")
    assert await pinned(rig) == {} and not rig.upstream.requests


async def test_apply_pins_the_campus_venues_without_the_network(rig: Rig) -> None:
    await run(rig, apply=True)
    found = await pinned(rig)
    assert {"kinosaal-9-133", "maker-space-9-229", "fsi-9-u09", "texoversum"} <= set(found)
    lat, lon, source, precision = found["kinosaal-9-133"]
    assert source == "import" and precision == "building" and 48.47 < float(lat) < 48.49
    assert "hochschule-reutlingen" not in found and not rig.upstream.requests


async def test_a_private_venue_stays_hidden(rig: Rig) -> None:
    outcomes = await run(rig, apply=True, private="kinosaal-9-133")
    assert outcomes["kinosaal-9-133"][1] == "unverändert"
    assert "kinosaal-9-133" not in await pinned(rig)


async def test_live_asks_one_request_per_slot_and_pins_the_answers(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        rig.slot.expire()

    monkeypatch.setattr(pin_venues.asyncio, "sleep", sleep)
    await run(rig, apply=True, live=True)
    found = await pinned(rig)
    assert found["davos"][2:] == ("nominatim", "building")
    assert found["hochschule-reutlingen"][2] == "nominatim"
    asked = [r.url.params["q"] for r in rig.upstream.requests]
    assert len(asked) == len(set(asked)) and "davos" in asked
    assert waits and set(waits) == {pin_venues.SLOT_WAIT}
    assert all(r.url.host == "nominatim.openstreetmap.org" for r in rig.upstream.requests)


def test_live_needs_apply_and_a_contact() -> None:
    for argv in (["--live"], ["--live", "--apply"], ["--live", "--contact", "x"]):
        with pytest.raises(SystemExit):
            pin_venues.parse(argv)
    assert pin_venues.parse(["--live", "--apply", "--contact", "x"]).live
