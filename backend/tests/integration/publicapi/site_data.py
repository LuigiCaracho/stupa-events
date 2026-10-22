"""A fixed set of events for the site routes: three categories, three organizations, two months.

Built through the real API. Titles carry the words the search tests look for. The draft and the
withdrawn event must never show up anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.publicapi import clock
from app.settings import get_settings
from tests._support.factories import make_settings
from tests.integration.events.harness import Api, future

INDEX = Path(__file__).resolve().parents[2] / "fixtures" / "spa-index.html"
BASE = "https://events.example"


@dataclass
class Site:
    """Ids and slugs of the events by short name."""

    ids: dict[str, str] = field(default_factory=dict)
    slugs: dict[str, str] = field(default_factory=dict)


def configure(api: Api, **settings: Any) -> None:
    """Point the app at the SPA fixture and a fixed public base URL."""
    cfg = make_settings(**{"spa_index_path": str(INDEX), "public_base_url": BASE, **settings})
    api.app.dependency_overrides[get_settings] = lambda: cfg


def freeze(api: Api, moment: datetime) -> None:
    """Replace the public clock."""
    api.app.dependency_overrides[clock.now] = lambda: moment


def at(days: int, hours: int = 2) -> dict[str, str]:
    """Start and end of an event `days` ahead."""
    return {"startsAt": future(days).isoformat(), "endsAt": future(days, hours).isoformat()}


async def add(
    api: Api,
    site: Site,
    key: str,
    *,
    state: str = "published",
    poster: bool = False,
    user: str = "organizer-fsi",
    org: str = "fsi",
    **over: Any,
) -> dict:
    """Create one event and publish it; the poster is attached before publishing."""
    event = await api.create_event(user=user, org=org, **over)
    eid = event["id"]
    if poster:
        await api.with_poster(eid, user)
    if state != "draft":
        await api.confirm_location(eid)
        assert (await api.act(user, eid, "publish")).status_code == 200
    current = await api.get("editor", eid)
    site.ids[key], site.slugs[key] = eid, current["slug"]
    return current


async def seed(api: Api) -> Site:
    """Create the standard set and return its ids."""
    site = Site()
    cat = api.category_ids
    await add(
        api,
        site,
        "movie",
        title="Movienight Kinoabend",
        poster=True,
        summary="Ein Film im Saal.",
        primaryCategoryId=cat["kino"],
        **at(10),
    )
    await api.sql(
        "UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'movienight'), "
        "ticket_url = 'https://tickets.example/x' WHERE id = :e",
        e=site.ids["movie"],
    )
    makers = {"user": "organizer-makers", "org": "makers"}
    await add(
        api,
        site,
        "karaoke",
        title="Karaoke im Rappen",
        summary="Singen bis spät.",
        primaryCategoryId=cat["party"],
        **makers,
        **at(12),
    )
    await add(
        api,
        site,
        "fsi",
        title="Fachschaftssitzung FSI",
        primaryCategoryId=cat["fachschaft-informatik-fsi"],
        **at(45),
    )
    await add(
        api,
        site,
        "cafe",
        title="Treff im Café",
        summary="Kaffee und Kuchen.",
        primaryCategoryId=cat["kino"],
        **at(46),
    )
    ski = await add(
        api, site, "ski", title="Skiausfahrt", primaryCategoryId=cat["party"], **makers, **at(20)
    )
    cancel = await api.act(
        "organizer-makers", ski["id"], "cancel", reason="x", publicReasonCode="weather"
    )
    assert cancel.status_code == 200, cancel.text
    await add(
        api,
        site,
        "past",
        title="Rückblick Party",
        poster=True,
        primaryCategoryId=cat["party"],
        **at(5),
    )
    await api.sql(
        "UPDATE event SET starts_at = starts_at - interval '40 days', "
        "ends_at = ends_at - interval '40 days' WHERE id = :e",
        e=site.ids["past"],
    )
    await add(api, site, "draft", state="draft", title="Geheimer Entwurf", **at(8))
    gone = await add(api, site, "gone", title="Zurückgezogen", **at(9))
    assert (await api.act("organizer-fsi", gone["id"], "unpublish")).status_code == 200
    return site
