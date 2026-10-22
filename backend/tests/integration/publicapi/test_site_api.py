"""The site routes over HTTP against the real view: list, facets, detail, today, calendar, archive."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema_rs
import pytest

from app.modules.publicapi.clock import BERLIN
from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration
API = "/api/public"
CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "schema" / "public-site-v1.json").read_text()
)
VALIDATORS = {name: jsonschema_rs.validator_for(schema) for name, schema in CONTRACT.items()}
ROUTE_SCHEMA = {
    "/events": "search",
    "/today": "today",
    "/categories": "categories",
    "/calendar": "calendar",
    "/archive": "archive",
}


@pytest.fixture
async def site(api: Api) -> Site:
    site_data.configure(api)
    return await site_data.seed(api)


async def get(api: Api, path: str, **params: Any) -> dict:
    response = await api.request(None, "GET", f"{API}{path}", params=params)
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    body = response.json()
    name = ROUTE_SCHEMA.get(path, "detail" if path.startswith("/events/") else None)
    if name:
        VALIDATORS[name].validate(body)
    return body


def slugs(body: dict) -> list[str]:
    return [item["slug"] for item in body["items"]]


async def test_the_list_shows_upcoming_public_events_only(api: Api, site: Site) -> None:
    body = await get(api, "/events")
    shown = slugs(body)
    for key in ("movie", "karaoke", "fsi", "cafe", "ski"):
        assert site.slugs[key] in shown
    for key in ("draft", "gone", "past"):
        assert site.slugs[key] not in shown
    assert body["total"] == 5 and shown == sorted(shown, key=lambda s: s[:10])
    card = next(i for i in body["items"] if i["slug"] == site.slugs["movie"])
    assert card["path"] == f"/e/{site.slugs['movie']}" and card["image"]["url"].startswith("/api/")
    assert card["organization"] == {
        "slug": "fsi",
        "name": card["organization"]["name"],
        "short": "FSI",
    }
    ski = next(i for i in body["items"] if i["slug"] == site.slugs["ski"])
    assert ski["status"] == "cancelled" and ski["statusReason"]["code"] == "weather"


async def test_facets_are_disjunctive_and_only_on_the_first_page(api: Api, site: Site) -> None:
    body = await get(api, "/events")
    cats = {c["slug"]: c["count"] for c in body["facets"]["categories"]}
    assert cats["kino"] == 2 and cats["party"] == 2 and cats["fachschaft"] == 1
    assert cats["fachschaft-informatik-fsi"] == 1
    orgs = {o["slug"]: o["count"] for o in body["facets"]["organizations"]}
    assert orgs == {"fsi": 3, "makers": 2}
    assert sum(m["count"] for m in body["facets"]["months"]) == 5
    chosen = await get(api, "/events", category="kino")
    assert chosen["total"] == 2
    again = {c["slug"]: c["count"] for c in chosen["facets"]["categories"]}
    assert again["party"] == 2 and again["kino"] == 2
    orgs_after = {o["slug"]: o["count"] for o in chosen["facets"]["organizations"]}
    assert orgs_after == {"fsi": 2}
    page = await get(api, "/events", limit=2)
    second = await get(api, "/events", limit=2, cursor=page["nextCursor"])
    assert second["total"] is None and second["facets"] is None
    assert page["total"] == 5


async def test_parent_category_counts_children_and_filters_both(api: Api, site: Site) -> None:
    body = await get(api, "/events", category="fachschaft")
    assert slugs(body) == [site.slugs["fsi"]]


async def test_zero_count_selection_stays_in_the_facet(api: Api, site: Site) -> None:
    body = await get(api, "/events", category="kino", organization="makers")
    assert body["total"] == 0
    cats = {c["slug"]: c["count"] for c in body["facets"]["categories"]}
    assert cats["kino"] == 0 and cats["party"] == 2


async def test_cursor_walk_has_no_duplicates_and_no_gaps(api: Api, site: Site) -> None:
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = await get(api, "/events", **params)
        seen += slugs(body)
        cursor = body["nextCursor"]
        if cursor is None:
            break
    assert sorted(seen) == sorted(slugs(await get(api, "/events", limit=50)))
    assert len(seen) == len(set(seen)) == 5


async def test_dates_past_and_validation(api: Api, site: Site) -> None:
    past = await get(api, "/events", past=1)
    assert slugs(past) == [site.slugs["past"]]
    wide = await get(api, "/events", **{"from": "2020-01-01", "to": "2100-01-01"})
    assert site.slugs["past"] in slugs(wide) and site.slugs["draft"] not in slugs(wide)
    bad = await api.request(
        None, "GET", f"{API}/events", params={"from": "2026-05-02", "to": "2026-05-01"}
    )
    assert bad.status_code == 422
    junk = await api.request(None, "GET", f"{API}/events", params={"from": "kaputt"})
    assert junk.status_code == 422 and junk.headers["content-type"].startswith(
        "application/problem"
    )
    cursor = await api.request(None, "GET", f"{API}/events", params={"cursor": "###"})
    assert cursor.status_code == 422 and cursor.json()["code"] == "invalid_cursor"
    cross = await api.request(None, "GET", f"{API}/events", params={"q": "kino", "cursor": "e30="})
    assert cross.status_code == 422 and cross.json()["code"] == "invalid_cursor"
    long = await api.request(None, "GET", f"{API}/events", params={"q": "x" * 101})
    assert long.status_code == 422 and long.json()["code"] == "query_too_long"


async def test_detail_carries_the_public_fields_and_404_hides_drafts(api: Api, site: Site) -> None:
    body = await get(api, f"/events/{site.slugs['movie']}")
    assert body["ticketUrl"] == "https://tickets.example/x"
    assert body["icsUrl"] == f"/ics/e/{site.slugs['movie']}.ics" and body["isPast"] is False
    assert body["image"]["og"]["width"] == 1200 and body["image"]["thumb"]["url"].startswith(
        "/api/"
    )
    assert body["format"]["slug"] == "movienight" and isinstance(body["more"], list)
    for slug in (site.slugs["draft"], site.slugs["gone"], "nope", "Bad_Slug"):
        response = await api.request(None, "GET", f"{API}/events/{slug}")
        assert response.status_code == 404, slug
    past = await get(api, f"/events/{site.slugs['past']}")
    assert past["isPast"] is True


async def test_today_calendar_categories_and_archive(api: Api, site: Site) -> None:
    today = await get(api, "/today")
    assert today["truncated"] is False
    later = [i["slug"] for d in today["days"] for i in d["items"]]
    assert site.slugs["movie"] not in later and site.slugs["fsi"] not in later
    cats = await get(api, "/categories")
    by = {c["slug"]: c for c in cats}
    assert by["kino"]["upcomingCount"] == 2 and by["fachschaft"]["upcomingCount"] == 1
    assert by["kino"]["description"] == "Movienight und Filmabende"
    first = (await get(api, "/events"))["items"][0]["startsAt"]
    start = datetime.fromisoformat(first).astimezone(BERLIN).strftime("%Y-%m")
    month = await get(api, "/calendar", month=start)
    assert month["month"] == start and month["days"] and not month["truncated"]
    far = await api.request(None, "GET", f"{API}/calendar", params={"month": "2099-01"})
    assert far.status_code == 422
    archive = await get(api, "/archive")
    assert slugs(archive) == [site.slugs["past"]] and archive["years"] and archive["year"]
