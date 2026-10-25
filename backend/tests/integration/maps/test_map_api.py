"""The map routes over HTTP against the real view: rounding, what stays out, the campus counts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema_rs
import pytest

from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration
API = "/api/public"
CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "schema" / "public-map-v1.json").read_text()
)
EVENTS = jsonschema_rs.validator_for(CONTRACT["events"])
CAMPUS = jsonschema_rs.validator_for(CONTRACT["campus"])
LAT, LON = 48.482617, 9.187431
PINS = {
    "movie": ("exact", LAT, LON, False, "9"),
    "karaoke": ("building", LAT, LON, False, "9"),
    "ski": ("exact", 47.0, 10.0, False, None),
    "fsi": ("hidden", LAT, LON, False, "9"),
    "cafe": ("exact", LAT, LON, True, "9"),
    "draft": ("exact", LAT, LON, False, "9"),
    "gone": ("exact", LAT, LON, False, "9"),
}


@pytest.fixture
async def site(api: Api) -> Site:
    site_data.configure(api)
    found = await site_data.seed(api)
    await api.sql("DELETE FROM venue WHERE slug LIKE 'map-%'")
    for key, (precision, lat, lon, private, building) in PINS.items():
        await api.sql(
            "WITH v AS (INSERT INTO venue (slug, name, public_precision, lat, lon, is_private, "
            "building_no) VALUES (:s, :n, :p, :lat, :lon, :priv, :b) RETURNING id) "
            "UPDATE event SET venue_id = (SELECT id FROM v) WHERE id = :e",
            s=f"map-{key}",
            n=f"Ort {key}",
            p=precision,
            lat=lat,
            lon=lon,
            priv=private,
            b=building,
            e=found.ids[key],
        )
    yield found
    await api.sql(
        "UPDATE event SET venue_id = NULL WHERE venue_id IN (SELECT id FROM venue WHERE slug LIKE 'map-%')"
    )
    await api.sql("DELETE FROM venue WHERE slug LIKE 'map-%'")


async def get(api: Api, path: str, *, status: int = 200, **params: Any) -> dict:
    response = await api.request(None, "GET", f"{API}{path}", params=params)
    assert response.status_code == status, response.text
    assert "set-cookie" not in response.headers
    return response.json()


def by_slug(body: dict) -> dict[str, dict]:
    return {f["properties"]["slug"]: f for f in body["features"]}


async def test_only_public_pins_appear_and_they_are_rounded(api: Api, site: Site) -> None:
    body = await get(api, "/map/events")
    EVENTS.validate(body)
    found = by_slug(body)
    assert set(found) == {site.slugs[k] for k in ("movie", "karaoke", "ski")}
    assert found[site.slugs["movie"]]["geometry"]["coordinates"] == [LON, LAT]
    assert found[site.slugs["movie"]]["properties"]["precision"] == "exact"
    assert found[site.slugs["karaoke"]]["geometry"]["coordinates"] == [9.187, 48.483]
    assert found[site.slugs["karaoke"]]["properties"]["precision"] == "building"
    assert found[site.slugs["ski"]]["properties"]["status"] == "cancelled"
    assert found[site.slugs["movie"]]["properties"]["imageThumb"].startswith("/api/public/media/")
    assert body["truncated"] is False


async def test_nothing_hidden_or_private_leaks_into_any_map_body(api: Api, site: Site) -> None:
    raw = ""
    for path, params in (
        ("/map/events", {}),
        ("/map/events", {"past": 1}),
        ("/campus/buildings", {"from": "2000-01-01", "to": "2100-01-01"}),
        ("/campus/events", {"building": "9", "from": "2000-01-01", "to": "2100-01-01"}),
    ):
        raw += (await api.request(None, "GET", f"{API}{path}", params=params)).text
    assert "Ort cafe" not in raw and "Ort fsi" not in raw and "Geheimer Entwurf" not in raw
    assert site.slugs["fsi"] not in raw and site.slugs["cafe"] not in raw


async def test_the_filters_and_the_limit_cut_the_list(api: Api, site: Site) -> None:
    inside = await get(api, "/map/events", bbox="9.0,48.4,9.3,48.6")
    assert set(by_slug(inside)) == {site.slugs["movie"], site.slugs["karaoke"]}
    assert not (await get(api, "/map/events", bbox="0,0,1,1"))["features"]
    kino = await get(api, "/map/events", category="kino")
    assert set(by_slug(kino)) == {site.slugs["movie"]}
    cut = await get(api, "/map/events", limit=1)
    assert cut["truncated"] is True and len(cut["features"]) == 1
    past = await get(api, "/map/events", past=1)
    assert past["features"] == []


@pytest.mark.parametrize("bbox", ["x", "1,2,3", "9.3,48.4,9.1,48.6", "0,0,1,91"])
async def test_a_bad_bbox_is_a_problem(api: Api, site: Site, bbox: str) -> None:
    body = await get(api, "/map/events", status=422, bbox=bbox)
    assert body["status"] == 422


def window() -> dict[str, str]:
    today = datetime.now(UTC).date()
    return {"from": today.isoformat(), "to": (today + timedelta(days=60)).isoformat()}


async def test_the_campus_lists_every_building_with_the_count_of_the_range(
    api: Api, site: Site
) -> None:
    body = await get(api, "/campus/buildings", **window())
    CAMPUS.validate(body)
    buildings = {f["properties"]["buildingNo"]: f for f in body["features"]}
    assert len(buildings) >= 7 and buildings["9"]["geometry"]["type"] == "Polygon"
    assert buildings["9"]["properties"]["count"] == 2
    assert buildings["9"]["properties"]["approx"] is False
    assert buildings["1"]["properties"]["count"] == 0
    today = await get(api, "/campus/buildings")
    assert {f["properties"]["count"] for f in today["features"]} == {0}


async def test_the_building_list_answers_with_the_events_of_the_building(
    api: Api, site: Site
) -> None:
    body = await get(api, "/campus/events", building="9", **window())
    assert {i["slug"] for i in body["items"]} == {site.slugs["movie"], site.slugs["karaoke"]}
    assert body["total"] == 2 and body["facets"] is None
    empty = await get(api, "/campus/events", building="1", **window())
    assert empty["items"] == []
    await get(api, "/campus/events", status=404, building="99", **window())
    await get(api, "/campus/events", status=422, building="x9")
    await get(api, "/campus/events", status=422)


async def test_the_search_route_takes_a_building(api: Api, site: Site) -> None:
    body = await get(api, "/events", building="9")
    assert {i["slug"] for i in body["items"]} == {site.slugs["movie"], site.slugs["karaoke"]}
    assert (await get(api, "/events", building="1"))["items"] == []
