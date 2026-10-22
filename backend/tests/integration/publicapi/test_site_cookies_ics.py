"""No cookie on any public route, the XSRF cookie only with a session, and the one-event calendar."""

from __future__ import annotations

import pytest
from icalendar import Calendar

from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration


@pytest.fixture
async def site(api: Api) -> Site:
    site_data.configure(api)
    return await site_data.seed(api)


def paths(site: Site) -> list[str]:
    slug = site.slugs["movie"]
    return [
        "/api/public/events",
        "/api/public/events?q=kino",
        f"/api/public/events/{slug}",
        "/api/public/today",
        "/api/public/categories",
        "/api/public/calendar?month=2026-11",
        "/api/public/archive",
        f"/ics/e/{slug}.ics",
        "/",
        "/suche?q=geheim",
        "/kalender",
        "/rueckblick",
        f"/e/{slug}",
        "/e/unbekannt",
        "/k/kino",
        "/sitemap.xml",
        "/robots.txt",
        "/api/auth/me",
    ]


async def test_no_public_route_and_not_even_auth_me_sets_a_cookie_for_an_anonymous_visitor(
    api: Api, site: Site
) -> None:
    for path in paths(site):
        response = await api.request(None, "GET", path)
        assert "set-cookie" not in response.headers, path


async def test_a_signed_in_session_still_gets_the_xsrf_cookie(api: Api, site: Site) -> None:
    api.client.cookies.set("ev_session", "anything")
    me = await api.request("editor", "GET", "/api/auth/me")
    assert me.status_code == 200 and "XSRF-TOKEN" in me.headers["set-cookie"]
    shell = await api.request("editor", "GET", "/")
    assert "set-cookie" not in shell.headers
    api.client.cookies.clear()


async def test_the_single_event_calendar_is_a_download(api: Api, site: Site) -> None:
    slug = site.slugs["movie"]
    response = await api.request(None, "GET", f"/ics/e/{slug}.ics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert response.headers["content-disposition"] == f'attachment; filename="{slug}.ics"'
    assert response.headers["cache-control"] == "public, max-age=300" and response.headers["etag"]
    event = Calendar.from_ical(response.content).walk("VEVENT")[0]
    assert str(event["SUMMARY"]) == "Movienight Kinoabend" and str(event["UID"]).endswith(
        "@events.reutlingen.university"
    )
    again = await api.request(
        None, "GET", f"/ics/e/{slug}.ics", headers={"If-None-Match": response.headers["etag"]}
    )
    assert again.status_code == 304


async def test_cancelled_past_unknown_and_draft_calendars(api: Api, site: Site) -> None:
    ski = await api.request(None, "GET", f"/ics/e/{site.slugs['ski']}.ics")
    assert b"STATUS:CANCELLED" in ski.content
    assert (await api.request(None, "GET", f"/ics/e/{site.slugs['past']}.ics")).status_code == 200
    for slug in (site.slugs["draft"], site.slugs["gone"], "nope", "BAD_slug"):
        assert (await api.request(None, "GET", f"/ics/e/{slug}.ics")).status_code == 404, slug
