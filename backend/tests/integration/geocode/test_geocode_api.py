"""`POST /admin/venues/{id}/geocode` and the pin rules of `PATCH`: cache, slot, privacy, source."""

from __future__ import annotations

import pytest

from tests.integration.geocode.conftest import HIT, Rig

pytestmark = pytest.mark.integration
VENUES = "/api/admin/venues"
ADDRESS = {"address": "Alteburgstraße 150", "postcode": "72762", "city": "Reutlingen"}


async def make(rig: Rig, slug: str = "geo-a", **over: object) -> str:
    body = {"slug": slug, "name": "Ort", **ADDRESS, **over}
    made = await rig.api.request("editor", "POST", VENUES, json=body)
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def geocode(rig: Rig, venue: str, expected: int = 200) -> dict:
    response = await rig.api.request("editor", "POST", f"{VENUES}/{venue}/geocode")
    assert response.status_code == expected, response.text
    return response.json()


async def test_a_lookup_goes_out_once_and_the_answer_is_cached(rig: Rig) -> None:
    venue = await make(rig)
    first = await geocode(rig, venue)
    assert first["found"] and first["cached"] is False and first["lat"] == "48.482617"
    assert first["attribution"] == "© OpenStreetMap"
    (request,) = rig.upstream.requests
    assert request.url.host == "nominatim.openstreetmap.org" and request.url.path == "/search"
    assert request.url.params["q"] == "alteburgstraße 150, 72762 reutlingen"
    assert request.url.params["format"] == "jsonv2" and request.url.params["limit"] == "1"
    assert request.headers["user-agent"].startswith("STUPA-Events/")
    assert "kontakt@example.org" in request.headers["user-agent"]
    assert rig.slot.extended == 1
    rig.slot.expire()
    again = await geocode(rig, venue)
    assert again["cached"] is True and again["lat"] == first["lat"]
    assert len(rig.upstream.requests) == 1


async def test_nothing_is_stored_on_the_venue(rig: Rig) -> None:
    venue = await make(rig)
    await geocode(rig, venue)
    row = (await rig.api.request("editor", "GET", VENUES)).json()
    mine = next(v for v in row if v["id"] == venue)
    assert mine["lat"] is None and mine["geocodeSource"] is None


async def test_a_miss_is_cached_too(rig: Rig) -> None:
    rig.upstream.body = []
    venue = await make(rig)
    first = await geocode(rig, venue)
    assert first == {**first, "found": False, "lat": None, "cached": False}
    rig.slot.expire()
    assert (await geocode(rig, venue))["cached"] is True
    assert len(rig.upstream.requests) == 1


async def test_a_second_lookup_inside_two_seconds_is_refused(rig: Rig) -> None:
    first = await make(rig, "geo-a")
    second = await make(rig, "geo-b", address="Pestalozzistraße 52")
    await geocode(rig, first)
    response = await rig.api.request("editor", "POST", f"{VENUES}/{second}/geocode")
    assert response.status_code == 429 and response.json()["code"] == "geocode_rate"
    assert response.headers["retry-after"] == "2"
    rig.slot.expire()
    await geocode(rig, second)
    assert len(rig.upstream.requests) == 2


async def test_a_cache_hit_needs_no_slot(rig: Rig) -> None:
    first = await make(rig, "geo-a")
    twin = await make(rig, "geo-b")
    await geocode(rig, first)
    assert (await geocode(rig, twin))["cached"] is True


@pytest.mark.parametrize("broken", [True, None])
async def test_without_redis_the_lookup_is_refused(rig: Rig, broken: bool | None) -> None:
    from tests.integration.geocode.conftest import get_slot_redis

    venue = await make(rig)
    if broken:
        rig.slot.broken = True
    else:
        rig.api.app.dependency_overrides[get_slot_redis] = lambda: None
    body = await geocode(rig, venue, 503)
    assert body["code"] == "geocode_unavailable" and not rig.upstream.requests


async def test_a_private_venue_is_refused_before_any_network_access(rig: Rig) -> None:
    venue = await make(rig, isPrivate=True)
    body = await geocode(rig, venue, 422)
    assert body["code"] == "venue_private" and not rig.upstream.requests
    assert not rig.slot.taken


async def test_incomplete_address_unknown_venue_and_disabled(rig: Rig) -> None:
    bare = await make(rig, "geo-bare", address=None, postcode=None)
    assert (await geocode(rig, bare, 422))["code"] == "address_incomplete"
    missing = "00000000-0000-0000-0000-000000000000"
    assert (
        await rig.api.request("editor", "POST", f"{VENUES}/{missing}/geocode")
    ).status_code == 404
    rig.configure(nominatim_enabled=False, nominatim_contact=None)
    venue = await make(rig)
    assert (await geocode(rig, venue, 503))["code"] == "geocode_disabled"
    assert not rig.upstream.requests


async def test_only_the_nominatim_host_is_ever_called(rig: Rig) -> None:
    rig.configure(nominatim_base_url="https://evil.example")
    venue = await make(rig)
    assert (await geocode(rig, venue, 503))["code"] == "geocode_unavailable"
    assert not rig.upstream.requests


async def test_an_upstream_failure_is_a_503_and_not_cached(rig: Rig) -> None:
    rig.upstream.status = 500
    venue = await make(rig)
    assert (await geocode(rig, venue, 503))["code"] == "geocode_unavailable"
    rows = await rig.api.sql("SELECT count(*) FROM geocode_cache")
    assert rows == [(0,)]


async def test_the_audit_entry_names_the_venue_but_not_the_address(rig: Rig) -> None:
    venue = await make(rig)
    await geocode(rig, venue)
    rows = await rig.api.sql(
        "SELECT target_id, data::text FROM audit_entry WHERE action = 'venue_geocode'"
    )
    assert rows == [(venue, '{"found": true}')]
    assert "Alteburg" not in rows[0][1]


async def test_the_editor_needs_the_venue_permission(rig: Rig) -> None:
    venue = await make(rig)
    for user in ("member", "organizer-fsi"):
        denied = await rig.api.request(user, "POST", f"{VENUES}/{venue}/geocode")
        assert denied.status_code == 403, user


async def test_nominatim_is_recorded_only_for_the_cached_answer(rig: Rig) -> None:
    venue = await make(rig)
    await geocode(rig, venue)
    pin = {"lat": 48.482617, "lon": 9.187431, "publicPrecision": "building"}
    ok = await rig.api.request(
        "editor", "PATCH", f"{VENUES}/{venue}", json={**pin, "geocodeSource": "nominatim"}
    )
    assert ok.json()["geocodeSource"] == "nominatim"
    moved = await rig.api.request(
        "editor",
        "PATCH",
        f"{VENUES}/{venue}",
        json={"lat": 48.5, "lon": 9.2, "geocodeSource": "nominatim"},
    )
    assert moved.json()["geocodeSource"] == "pin"
    plain = await rig.api.request("editor", "PATCH", f"{VENUES}/{venue}", json=pin)
    assert plain.json()["geocodeSource"] == "pin"


async def test_a_private_venue_never_gets_nominatim_as_source(rig: Rig) -> None:
    venue = await make(rig)
    await geocode(rig, venue)
    private = await rig.api.request(
        "editor",
        "PATCH",
        f"{VENUES}/{venue}",
        json={"lat": 48.482617, "lon": 9.187431, "isPrivate": True, "geocodeSource": "nominatim"},
    )
    assert private.json()["geocodeSource"] == "pin"


async def test_nominatim_without_a_cached_answer_is_a_pin(rig: Rig) -> None:
    venue = await make(rig)
    pinned = await rig.api.request(
        "editor",
        "PATCH",
        f"{VENUES}/{venue}",
        json={"lat": 48.4, "lon": 9.1, "geocodeSource": "nominatim"},
    )
    assert pinned.json()["geocodeSource"] == "pin"
    invalid = await rig.api.request(
        "editor",
        "PATCH",
        f"{VENUES}/{venue}",
        json={"lat": 48.4, "lon": 9.1, "geocodeSource": "import"},
    )
    assert invalid.status_code == 422


async def test_a_public_precision_needs_a_coordinate_or_a_building(rig: Rig) -> None:
    venue = await make(rig)
    for precision in ("exact", "building"):
        refused = await rig.api.request(
            "editor", "PATCH", f"{VENUES}/{venue}", json={"publicPrecision": precision}
        )
        assert refused.status_code == 422 and refused.json()["code"] == "coordinates_missing"
    ok = await rig.api.request(
        "editor",
        "PATCH",
        f"{VENUES}/{venue}",
        json={"publicPrecision": "building", "buildingNo": "9"},
    )
    assert ok.status_code == 200
    unrelated = await rig.api.request("editor", "PATCH", f"{VENUES}/{venue}", json={"notes": "x"})
    assert unrelated.status_code == 200
    created = await rig.api.request(
        "editor", "POST", VENUES, json={"slug": "geo-x", "name": "X", "publicPrecision": "exact"}
    )
    assert created.status_code == 422 and created.json()["code"] == "coordinates_missing"


def test_the_fixture_answer_has_the_fields_the_client_reads() -> None:
    assert {"lat", "lon", "display_name", "osm_type", "osm_id"} <= HIT[0].keys()
