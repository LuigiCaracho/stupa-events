"""Edge branches of the archive: "last time" fallbacks, thin dossiers, odd inputs."""

from __future__ import annotations

import pytest

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def test_last_time_is_null_without_a_source_and_falls_back_to_the_format(api: Api) -> None:
    plain = await api.create_event(title="Neu ohne Format")
    empty = await api.request("organizer-fsi", "GET", f"/api/events/{plain['id']}/last-time")
    assert empty.status_code == 200 and empty.json() is None
    older = await archived_movienight(api, title="Ältere Ausgabe", days_ago=200)
    newest = await api.create_event(title="Neue Ausgabe")
    headers = {"If-Match": f'"{newest["rev"]}"'}
    await ok(
        await api.request(
            "organizer-fsi",
            "PUT",
            f"/api/events/{newest['id']}/format",
            json={"slug": "movienight"},
            headers=headers,
        )
    )
    last = await ok(
        await api.request("organizer-fsi", "GET", f"/api/events/{newest['id']}/last-time")
    )
    assert last["source"]["id"] == older and last["attendance"] == 87
    first_ever = await api.create_event(title="Nur Format", startsAt=future(1).isoformat())
    await ok(
        await api.request(
            "organizer-fsi",
            "PUT",
            f"/api/events/{first_ever['id']}/format",
            json={"slug": "campusfest"},
            headers={"If-Match": f'"{first_ever["rev"]}"'},
        )
    )
    none = await api.request("organizer-fsi", "GET", f"/api/events/{first_ever['id']}/last-time")
    assert none.json() is None


async def test_an_unreadable_origin_falls_back_to_the_previous_edition(api: Api) -> None:
    older = await archived_movienight(api, title="Ältere Ausgabe", days_ago=200)
    other = await archived_movienight(api, title="Andere Ausgabe", days_ago=90)
    clone = await api.request(
        "organizer-makers",
        "POST",
        f"/api/events/{other}/clone",
        json={"startsAt": future(40).isoformat()},
    )
    made = clone.json()["event"]
    await api.sql("UPDATE event SET state = 'live' WHERE id = :e", e=other)
    last = await ok(
        await api.request("organizer-makers", "GET", f"/api/events/{made['id']}/last-time")
    )
    assert last["source"]["id"] == older


async def test_the_archive_view_of_a_thin_dossier(api: Api) -> None:
    eid = await archived_movienight(api)
    await api.sql(
        "UPDATE event SET primary_category_id = NULL, format_id = NULL, venue_text = NULL, "
        "outcome = NULL WHERE id = :e",
        e=eid,
    )
    view = await ok(await api.request("member", "GET", f"/api/archive/{eid}"))
    assert view["category"] is None and view["format"] is None and view["venueName"] is None
    assert view["attendance"] is None


async def test_search_helpers_for_odd_inputs(api: Api) -> None:
    await archived_movienight(api)
    short = await ok(await api.request("member", "GET", "/api/search", params={"q": "abc"}))
    assert short["suggestion"] is None and short["total"] == 0
    syntax = await ok(await api.request("member", "GET", "/api/search", params={"q": '"Whiplash"'}))
    assert syntax["total"] == 1
    both = await ok(
        await api.request("member", "GET", "/api/search", params={"q": "whiplash OR zzz"})
    )
    assert both["total"] == 1
    filtered = await ok(
        await api.request(
            "member",
            "GET",
            "/api/search",
            params={"q": "whiplash", "category": "kino", "format": "movienight", "org": "fsi"},
        )
    )
    assert filtered["total"] == 1
    none = await ok(
        await api.request(
            "member", "GET", "/api/search", params={"q": "whiplash", "category": "party"}
        )
    )
    assert none["total"] == 0
    formats = await ok(
        await api.request(
            "member",
            "GET",
            "/api/search",
            params={"q": "movienight", "scope": "formats", "org": "fsi"},
        )
    )
    assert formats["total"] == 2 and formats["hits"][0]["format"] is not None
    docs = await ok(
        await api.request(
            "member",
            "GET",
            "/api/search",
            params={"q": "Aufbau", "scope": "documents", "year": 2026},
        )
    )
    assert docs["hits"] and docs["hits"][0]["link"].startswith("/archiv/")
    master = await api.request("editor", "POST", "/api/formats/movienight/howto", json={})
    assert master.status_code == 201
    found = await ok(
        await api.request(
            "member", "GET", "/api/search", params={"q": "Vorbereitung", "scope": "documents"}
        )
    )
    assert found["hits"][0]["link"] == "/formate/movienight"
