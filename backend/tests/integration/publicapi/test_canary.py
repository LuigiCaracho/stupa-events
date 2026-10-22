"""The canary test (E39, E41): no internal string in any public or foreign-facing byte."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import pytest
from httpx import Response

from tests._support.canary import (
    AMOUNT_DIGITS,
    FORMAT_ONLY,
    INTERNAL,
    PUBLIC_SUMMARY,
    PUBLIC_TITLE,
    drop_canary_format,
    internal_bits,
    mark,
    seed_canary,
)
from tests.integration.events.harness import Api
from worker.advance import archive_ended

pytestmark = pytest.mark.integration
FOREIGN = ("member", "organizer-makers", "viewer-tec")


@pytest.fixture(autouse=True)
async def clean_taxonomy_rows(api: Api):  # noqa: ANN201
    """Remove what the canary leaves in tables that the event wipe keeps."""
    drop = (
        "UPDATE event SET venue_id = NULL WHERE venue_id IN "
        "(SELECT id FROM venue WHERE slug LIKE 'canary-%')"
    )
    await api.sql(drop)
    await api.sql("DELETE FROM venue WHERE slug LIKE 'canary-%'")
    await drop_canary_format(api)
    yield
    await drop_canary_format(api)
    await api.sql("UPDATE organization SET contact_public = NULL")
    await api.sql(drop)
    await api.sql("DELETE FROM venue WHERE slug LIKE 'canary-%'")


def leaks(*responses: Response, public: bool = True) -> list[str]:
    found = []
    for response in responses:
        body = response.content.decode("utf-8", "replace") + str(dict(response.headers))
        if FORMAT_ONLY in body and public:
            found.append(f"{response.request.url}: {FORMAT_ONLY}")
        if INTERNAL in body:
            found.append(f"{response.request.url}: {INTERNAL}")
        if re.search(rf"(?<![0-9a-f]){AMOUNT_DIGITS}(?![0-9a-f])", body):
            found.append(f"{response.request.url}: {AMOUNT_DIGITS}")
    return found


async def public_responses(api: Api, slugs: list[str]) -> list[Response]:
    base = "/api/public/feed/events"
    responses = []
    cursor = None
    while True:
        page = await api.request(
            None, "GET", base, params={"limit": 2, **({"cursor": cursor} if cursor else {})}
        )
        responses.append(page)
        cursor = page.json().get("nextCursor")
        if not cursor:
            break
    for params in (
        {"since": "0001-01-01T00:00:00Z"},
        {"limit": 0},
        {"cursor": "###"},
        {"since": "gestern"},
        {"from": "nonsense"},
        {"organization": "fsi"},
        {"org": "makers", "organization": "fsi"},
    ):
        responses.append(await api.request(None, "GET", base, params=params))
    responses += [await api.request(None, "GET", base, params={"category": slug}) for slug in slugs]
    responses.append(await api.request(None, "GET", "/ics/all.ics"))
    responses += [await api.request(None, "GET", f"/ics/k/{slug}.ics") for slug in slugs]
    responses += [
        await api.request(None, "GET", path) for path in ("/ics/k/nope.ics", "/ics/k/BAD.ics")
    ]
    return responses


async def site_responses(api: Api, event_slugs: list[str], slugs: list[str]) -> list[Response]:
    get = lambda path, **params: api.request(None, "GET", path, params=params)  # noqa: E731
    out = [
        await get("/api/public/events"),
        await get("/api/public/events", q="CANARY"),
        await get("/api/public/events", q="CANARY-INTERNAL"),
        await get("/api/public/events", q="FORMATDESC"),
        await get("/api/public/events", past=1),
        await get("/api/public/events", organization="fsi", category="kino"),
        await get("/api/public/events", cursor="###"),
        await get("/api/public/events", **{"from": "kaputt"}),
        await get("/api/public/today"),
        await get("/api/public/categories"),
        await get("/api/public/archive"),
        await get("/api/public/calendar", month=datetime.now().strftime("%Y-%m")),
        await get("/api/public/calendar", month="1999-01"),
        await get("/ics/all.ics"),
        await get("/", q="CANARY"),
        await get("/suche", q="CANARY"),
        await get("/kalender"),
        await get("/rueckblick"),
        await get("/sitemap.xml"),
        await get("/robots.txt"),
    ]
    for slug in event_slugs + ["nope"]:
        out += [
            await get(f"/api/public/events/{slug}"),
            await get(f"/ics/e/{slug}.ics"),
            await get(f"/e/{slug}"),
        ]
    for slug in slugs:
        out += [await get(f"/k/{slug}"), await get("/api/public/events", category=slug)]
    return out


async def category_slugs(api: Api) -> list[str]:
    return [row[0] for row in await api.sql("SELECT slug FROM category ORDER BY slug")]


async def test_nothing_internal_reaches_the_anonymous_feed_or_a_calendar(api: Api) -> None:
    await seed_canary(api)
    responses = await public_responses(api, await category_slugs(api))
    assert not leaks(*responses)
    feed = (
        await api.request(None, "GET", "/api/public/feed/events", params={"limit": 500})
    ).content.decode()
    assert PUBLIC_TITLE in feed and PUBLIC_SUMMARY in feed and "CANARY-PUBLIC-DESCRIPTION" in feed
    calendar = (await api.request(None, "GET", "/ics/all.ics")).content.decode()
    assert PUBLIC_TITLE in calendar and "CANARY-PUBLIC-VENUE" in calendar
    media = json_urls(feed)
    assert media
    for url in media:
        assert not leaks(await api.request(None, "GET", url))
    assert not leaks(
        await api.request(None, "GET", "/api/public/media/ffffffffffffffff-card_1200.webp")
    )


def json_urls(feed: str) -> list[str]:
    import json

    return [
        item["image"]["url"].removeprefix("http://localhost:8081")
        for item in json.loads(feed)["items"]
        if item["image"]
    ]


async def test_unconfirmed_text_and_private_addresses_never_reach_the_public(api: Api) -> None:
    canary = await seed_canary(api)
    items = {
        i["id"]: i
        for i in (
            await api.request(None, "GET", "/api/public/feed/events", params={"limit": 500})
        ).json()["items"]
    }
    assert (
        items[canary.hidden_text]["venueText"] is None
        and items[canary.hidden_text]["venue"] is None
    )
    assert items[canary.private_venue]["venue"] == {
        "name": "Treffpunkt auf Anfrage",
        "address": None,
        "city": None,
    }
    assert items[canary.hidden_venue]["venue"] == {
        "name": "Saal Hidden",
        "address": None,
        "city": None,
    }
    assert not any(draft in items for draft in canary.drafts)


async def foreign_requests(api: Api, user: str, canary: Any) -> list[Response]:
    docs = [
        str(r[0])
        for r in await api.sql("SELECT id FROM document WHERE event_id = :e", e=canary.archived)
    ]
    files = [
        str(r[0])
        for r in await api.sql("SELECT id FROM attachment WHERE event_id = :e", e=canary.archived)
    ]
    get = lambda path, **params: api.request(user, "GET", path, params=params)  # noqa: E731
    out = [
        await get(f"/api/archive/{canary.archived}"),
        await get(f"/api/archive/{canary.published}"),
        await get("/api/library", limit=50),
        await get("/api/library", q="CANARY"),
        await get("/api/library", q="TEAMFILE"),
        await get("/api/templates", q="CANARY"),
        await get("/api/templates"),
        await get(f"/api/events/{canary.archived}/clone-preview"),
        await get(f"/api/events/{canary.archived}/last-time"),
        await get("/api/formats/movienight"),
        await get("/api/formats"),
        await get(f"/api/events/{canary.archived}"),
        await get(f"/api/events/{canary.archived}/quotes"),
        await get(f"/api/events/{canary.archived}/documents"),
        await get(f"/api/events/{canary.archived}/comments"),
    ]
    for scope in ("events", "documents", "formats"):
        for q in ("CANARY", "CANARY-INTERNAL", "TEAMFILE", "DOCORG", "Kontext"):
            out.append(await get("/api/search", q=q, scope=scope, limit=50))
    out += [await get(f"/api/documents/{d}") for d in docs]
    out += [await get(f"/api/attachments/{f}/download") for f in files]
    out += [await get(f"/api/attachments/{f}/preview") for f in files]
    return out


async def test_foreign_readers_find_no_internal_string_and_no_amount(api: Api) -> None:
    await api.add_user("viewer-tec", {"events-tec-viewer": ("viewer", "tec")})
    canary = await seed_canary(api)
    for user in FOREIGN:
        responses = await foreign_requests(api, user, canary)
        assert not leaks(*responses, public=False), user
    shared = await api.request("member", "GET", f"/api/archive/{canary.archived}")
    assert "CANARY-PUBLIC-SHARED" in shared.text and "CANARY-PUBLIC-ARCHIVED" in shared.text
    found = await api.request(
        "member", "GET", "/api/search", params={"q": "CANARY-PUBLIC-SHARED", "scope": "documents"}
    )
    assert found.json()["total"] == 1


async def test_the_own_organization_does_find_its_own_strings(api: Api) -> None:
    canary = await seed_canary(api)
    docs = await api.request(
        "organizer-fsi", "GET", "/api/search", params={"q": mark("DOCORG"), "scope": "documents"}
    )
    assert docs.json()["total"] >= 1 and mark("DOCORG") in docs.text
    team = await api.request(
        "organizer-fsi", "GET", "/api/search", params={"q": mark("DOCTEAM"), "scope": "documents"}
    )
    assert team.json()["total"] >= 1
    preview = await api.request(
        "organizer-fsi", "GET", f"/api/events/{canary.archived}/clone-preview"
    )
    assert mark("OUTCOMENOTES") in preview.text and str(AMOUNT_DIGITS) in preview.text
    submitter_team = await api.request(
        "viewer-fsi", "GET", "/api/search", params={"q": mark("DOCTEAM"), "scope": "documents"}
    )
    assert mark("DOCTEAM") not in [h["title"] for h in submitter_team.json()["hits"]]


async def test_canary_freedom_after_each_lifecycle_step(api: Api) -> None:
    event = await api.to_state("draft", title="Wandel")
    eid = event["id"]
    slugs = await category_slugs(api)

    async def clean() -> None:
        assert not leaks(*await public_responses(api, slugs))

    await clean()
    await api.confirm_location(eid)
    assert (await api.act("editor", eid, "publish")).status_code == 200
    await internal_bits(api, eid)
    await clean()
    cancelled = await api.act(
        "editor",
        eid,
        "cancel",
        reason=mark("CANCELNOTE"),
        publicReasonCode="room",
        publicReasonText="Raum weg",
    )
    assert cancelled.status_code == 200
    await clean()
    await api.act("editor", eid, "reinstate", reason=mark("REVNOTE"))
    ended = datetime.fromisoformat((await api.get("editor", eid))["endsAt"])
    await archive_ended(
        {"advance_sessionmaker": api.maker, "redis": api.pool}, now=ended + timedelta(hours=13)
    )
    await clean()
    feed = (await api.request(None, "GET", "/api/public/feed/events")).content.decode()
    assert "Wandel" in feed
    assert (await api.act("editor", eid, "restore")).status_code == 200
    await clean()
    feed = (await api.request(None, "GET", "/api/public/feed/events")).content.decode()
    assert "Wandel" not in feed


async def test_every_state_reaches_the_view_only_when_allowed(api: Api) -> None:
    ids = {
        "draft": (await api.to_state("draft", title="Zustand draft"))["id"],
        "published": (await api.to_state("published", title="Zustand published"))["id"],
        "archived": (await api.to_state("archived", title="Zustand archived"))["id"],
    }
    shown = {
        i["id"]
        for i in (
            await api.request(None, "GET", "/api/public/feed/events", params={"limit": 500})
        ).json()["items"]
    }
    assert {s for s, i in ids.items() if i in shown} == {"published", "archived"}
    ics = (await api.request(None, "GET", "/ics/all.ics")).content.decode()
    assert {s for s, i in ids.items() if f"UID:{i}@" in ics} == {"published", "archived"}


async def test_nothing_internal_reaches_the_site_routes_or_the_html_shell(api: Api) -> None:
    from tests.integration.publicapi import site_data

    site_data.configure(api)
    canary = await seed_canary(api)
    ids = [canary.published, canary.archived, canary.hidden_text, canary.private_venue]
    ids += [canary.hidden_venue, *canary.drafts]
    slugs = [r[0] for r in await api.sql("SELECT slug FROM event WHERE id = ANY(:ids)", ids=ids)]
    responses = await site_responses(api, slugs, await category_slugs(api))
    assert not leaks(*responses)
    by_url = {str(r.request.url): r for r in responses}
    listing = by_url["http://test/api/public/events"].text
    assert PUBLIC_TITLE in listing and PUBLIC_SUMMARY in listing
    published_slug = (await api.sql("SELECT slug FROM event WHERE id = :e", e=canary.published))[0][
        0
    ]
    detail = by_url[f"http://test/api/public/events/{published_slug}"].text
    assert "CANARY-PUBLIC-DESCRIPTION" in detail and "CANARY-PUBLIC-VENUE" in detail
    shell = by_url[f"http://test/e/{published_slug}"].text
    assert PUBLIC_TITLE in shell and "CANARY-PUBLIC-VENUE" in shell
    calendar = by_url[f"http://test/ics/e/{published_slug}.ics"].text
    assert PUBLIC_TITLE in calendar
    draft_slugs = [
        r[0]
        for r in await api.sql("SELECT slug FROM event WHERE id = ANY(:ids)", ids=canary.drafts)
    ]
    for slug in draft_slugs:
        assert by_url[f"http://test/api/public/events/{slug}"].status_code == 404
        assert by_url[f"http://test/e/{slug}"].status_code == 404
