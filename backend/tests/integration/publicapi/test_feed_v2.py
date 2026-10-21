"""Feed schema 2 over HTTP: fields, cursor, `since`, filters, venue rules and `textHtml`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema_rs
import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration
SCHEMA = jsonschema_rs.validator_for(
    json.loads((Path(__file__).resolve().parents[2] / "schema" / "feed-v2.json").read_text())
)


async def feed(api: Api, **params: Any) -> dict:
    response = await api.request(None, "GET", "/api/public/feed/events", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    SCHEMA.validate(body)
    return body


async def published_event(api: Api, **over: Any) -> dict:
    return await api.to_state("published", **over)


async def test_a_full_item_carries_every_v2_field(api: Api) -> None:
    event = await published_event(
        api, costText="5 Euro", descriptionMd="**Fett** und [Link](https://a.example)"
    )
    await api.sql(
        "UPDATE event SET ticket_url = 'https://tickets.example/x', website_url = 'https://w.example', "
        "format_id = (SELECT id FROM format WHERE slug = 'movienight') WHERE id = :e",
        e=event["id"],
    )
    item = (await feed(api))["items"][0]
    assert item["costText"] == "5 Euro" and item["ticketUrl"] == "https://tickets.example/x"
    assert item["textHtml"].startswith("<p><strong>Fett</strong>")
    assert item["format"] == {"slug": "movienight", "title": "Movienight"}
    assert item["sequence"] == 1 and item["updatedAt"].endswith("Z")
    assert item["categories"] == [{"slug": "kino", "name": "Kino", "kind": "format"}]
    assert item["venue"] == {"name": "Kinosaal 9-133", "address": None, "city": None}
    assert item["startsOn"] is None and item["endsOn"] is None
    assert (await feed(api))["nextCursor"] is None


async def test_the_parent_category_follows_the_main_one_and_filters_both(api: Api) -> None:
    fsi_category = api.category_ids["fachschaft-informatik-fsi"]
    event = await published_event(api, primaryCategoryId=fsi_category)
    other = await published_event(api)
    item = next(i for i in (await feed(api))["items"] if i["id"] == event["id"])
    assert [c["slug"] for c in item["categories"]] == ["fachschaft-informatik-fsi", "fachschaft"]
    by_parent = await feed(api, category="fachschaft")
    assert [i["id"] for i in by_parent["items"]] == [event["id"]]
    by_main = await feed(api, category="kino")
    assert [i["id"] for i in by_main["items"]] == [other["id"]]


async def test_venue_rules_private_hidden_building_and_exact(api: Api) -> None:
    event = await published_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO venue (slug, name, address, postcode, city, public_precision, is_private) "
        "VALUES ('v-hidden', 'Saal A', 'Weg 1', '72762', 'Reutlingen', 'hidden', false), "
        "('v-building', 'Saal B', 'Weg 2', '72762', 'Reutlingen', 'building', false), "
        "('v-exact', 'Saal C', 'Weg 3', '72762', 'Reutlingen', 'exact', false), "
        "('v-private', 'Bei Ada', 'Privatweg 9', '72762', 'Reutlingen', 'exact', true)"
    )
    expectations = {
        "v-hidden": ("Saal A", {"name": "Saal A", "address": None, "city": None}),
        "v-building": ("Saal B", {"name": "Saal B", "address": None, "city": "Reutlingen"}),
        "v-exact": ("Saal C", {"name": "Saal C", "address": "Weg 3", "city": "Reutlingen"}),
        "v-private": (None, {"name": "Treffpunkt auf Anfrage", "address": None, "city": None}),
    }
    for slug, (text_value, venue) in expectations.items():
        await api.sql(
            "UPDATE event SET venue_id = (SELECT id FROM venue WHERE slug = :s) WHERE id = :e",
            s=slug,
            e=eid,
        )
        item = (await feed(api))["items"][0]
        assert item["venueText"] == text_value and item["venue"] == venue, slug
    blob = json.dumps(await feed(api))
    assert "Privatweg" not in blob and "Bei Ada" not in blob


async def test_cursor_paging_walks_every_item_once(api: Api) -> None:
    ids = []
    for i in range(5):
        event = await published_event(
            api,
            title=f"Termin {i}",
            startsAt=future(10 + i).isoformat(),
            endsAt=future(10 + i, 2).isoformat(),
        )
        ids.append(event["id"])
    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = await feed(api, **params)
        seen += [i["id"] for i in page["items"]]
        pages += 1
        cursor = page["nextCursor"]
        if cursor is None:
            break
    assert seen == ids and pages == 3
    broken = await api.request(None, "GET", "/api/public/feed/events", params={"cursor": "###"})
    assert broken.status_code == 422 and broken.json()["code"] == "invalid_cursor"


async def test_since_filters_by_update_time_and_demands_an_offset(api: Api) -> None:
    old = await published_event(api, title="Alt")
    await api.sql(
        "UPDATE event SET updated_at = now() - interval '3 days' WHERE id = :e", e=old["id"]
    )
    new = await published_event(api, title="Neu")
    since = (await api.sql("SELECT (now() - interval '1 day')::text"))[0][0]
    assert since
    body = await feed(api, since="2000-01-01T00:00:00Z")
    assert len(body["items"]) == 2
    stamp = (
        await api.sql("SELECT to_char(now() - interval '1 day', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')")
    )[0][0]
    recent = await feed(api, since=stamp)
    assert [i["id"] for i in recent["items"]] == [new["id"]]
    for bad in ("2026-10-20T09:00:00", "2026-10-20T09:00:00 02:00", "gestern"):
        response = await api.request(None, "GET", "/api/public/feed/events", params={"since": bad})
        assert response.status_code == 400 and response.json()["code"] == "invalid_since"
        assert "%2B02:00" in response.json()["detail"]
    encoded = await api.request(
        None, "GET", "/api/public/feed/events?since=2000-01-01T00:00:00%2B02:00"
    )
    assert encoded.status_code == 200


async def test_organization_filter_and_its_alias(api: Api) -> None:
    mine = await published_event(api)
    theirs = await api.to_state("published", user="organizer-makers", org="makers", title="Anders")
    assert theirs
    for name in ("organization", "org"):
        body = await feed(api, **{name: "fsi"})
        assert [i["id"] for i in body["items"]] == [mine["id"]]
    clash = await api.request(
        None, "GET", "/api/public/feed/events", params={"organization": "fsi", "org": "makers"}
    )
    assert clash.status_code == 422


async def test_all_day_items_carry_their_days_and_the_feed_has_the_cache_headers(api: Api) -> None:
    event = await api.to_state("published")
    await api.sql(
        "UPDATE event SET all_day = true, starts_on = date '2026-12-24', ends_on = date '2026-12-25', "
        "starts_at = timestamptz '2026-12-23 23:00+00', ends_at = timestamptz '2026-12-25 23:00+00' "
        "WHERE id = :e",
        e=event["id"],
    )
    response = await api.request(None, "GET", "/api/public/feed/events")
    item = response.json()["items"][0]
    assert item["allDay"] and item["startsOn"] == "2026-12-24" and item["endsOn"] == "2026-12-25"
    assert response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=60"
    assert response.headers["x-robots-tag"] == "noindex" and "set-cookie" not in response.headers
    again = await api.request(
        None, "GET", "/api/public/feed/events", headers={"If-None-Match": response.headers["etag"]}
    )
    assert again.status_code == 304


async def test_an_archived_event_stays_in_the_feed_with_its_format(api: Api) -> None:
    from tests.integration.archive.fixture import archived_movienight

    eid = await archived_movienight(api)
    item = next(i for i in (await feed(api))["items"] if i["id"] == eid)
    assert item["format"]["slug"] == "movienight" and item["image"] is not None
    assert "245" not in json.dumps(item) and "Hausmeister" not in json.dumps(item)
