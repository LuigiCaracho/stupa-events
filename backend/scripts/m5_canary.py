"""The canary of contract 10.1 on the dev stack: seed it and scan public and foreign answers.

The internal strings come from `tests/_support/canary.internal_bits`, written by SQL onto
two dev dossiers: one live (public title, summary and venue as positive canary) and one
archived Movienight edition. `public_requests` reads the feed page by page, with odd
parameters, per category, and every calendar; `foreign_requests` reads archive, library,
templates, search and the dossier routes as a person of another organization. A hit is
`CANARY-INTERNAL-` or the digits of the secret amount anywhere in body or headers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from scripts import m4_ops as ops
from scripts.m5_live import bump_feed, live
from tests._support.canary import AMOUNT_DIGITS, INTERNAL, PUBLIC_SUMMARY, internal_bits

PUBLIC_TITLE = "CANARY-PUBLIC-TITLE M5"


@dataclass(frozen=True)
class Seeded:
    """The two canary dossiers."""

    live: str
    archived: str


class _Sql:
    """The `sql` part of the test harness, on the dev database."""

    async def sql(self, statement: str, **params: object) -> list[tuple[Any, ...]]:
        return ops.query(statement, **params)


def seed(organizer: httpx.Client, archived: str) -> Seeded:
    """Publish a canary dossier and hang the internal strings on it and on `archived`."""
    eid = live(organizer, PUBLIC_TITLE, days=37)
    ops.query(
        "UPDATE event SET summary = :s, venue_text = 'CANARY-PUBLIC-VENUE' WHERE id = :e",
        s=PUBLIC_SUMMARY,
        e=eid,
    )
    for target in (eid, archived):
        if not ops.query(
            "SELECT 1 FROM quote WHERE event_id = :e AND vendor LIKE 'CANARY%'", e=target
        ):
            asyncio.run(internal_bits(_Sql(), target))  # type: ignore[arg-type]
    ops.query(
        "INSERT INTO document (event_id, kind, title, body_md, visibility) SELECT :e, 'notes',"
        " 'CANARY-PUBLIC-SHARED', 'CANARY-PUBLIC-SHARED', 'shared' WHERE NOT EXISTS (SELECT 1"
        " FROM document WHERE event_id = :e AND title = 'CANARY-PUBLIC-SHARED')",
        e=archived,
    )
    bump_feed()
    return Seeded(eid, archived)


def leaks(
    responses: list[httpx.Response], markers: tuple[str, ...] = (INTERNAL, AMOUNT_DIGITS)
) -> list[str]:
    """Return `url: marker` for each answer that carries an internal string or the amount."""
    found = []
    for response in responses:
        body = response.content.decode("utf-8", "replace") + str(dict(response.headers))
        found += [f"{response.request.url}: {m}" for m in markers if m in body]
    return found


def _slugs() -> list[str]:
    return [row[0] for row in ops.query("SELECT slug FROM category ORDER BY slug")]


def public_requests(client: httpx.Client) -> tuple[list[str], bool]:
    """Scan every anonymous answer; return the leaks and whether the positive canary shows."""
    base = "/api/public/feed/events"
    pages: list[httpx.Response] = []
    cursor = None
    while True:
        page = client.get(base, params={"limit": 50, **({"cursor": cursor} if cursor else {})})
        pages.append(page)
        cursor = page.json().get("nextCursor")
        if not cursor:
            break
    odd = [
        client.get(base, params=params)
        for params in (
            {"since": "0001-01-01T00:00:00Z"},
            {"limit": 0},
            {"cursor": "###"},
            {"since": "gestern"},
            {"organization": "fsi"},
        )
    ]
    slugs = _slugs()
    per_category = [client.get(base, params={"category": slug}) for slug in slugs]
    closed = [
        client.get(path)
        for path in (
            "/api/search?q=CANARY",
            "/api/archive/00000000-0000-0000-0000-000000000000",
            "/api/library",
            "/api/templates",
            "/ics/k/nope.ics",
        )
    ]
    calendar = client.get("/ics/all.ics")
    calendars = [client.get(f"/ics/k/{slug}.ics") for slug in slugs]
    feed = "".join(page.text for page in pages)
    positive = PUBLIC_TITLE in feed and PUBLIC_SUMMARY in feed and PUBLIC_TITLE in calendar.text
    return leaks([*pages, *odd, *closed, *per_category, calendar, *calendars]), positive


def foreign_requests(
    client: httpx.Client, canary: Seeded, *, foreign: bool
) -> tuple[list[str], int]:
    """Scan archive, library, templates, search and dossier routes as one person.

    A reader of the own organization (`foreign = False`, `viewer-fsi`: the dev IdP has no
    foreign viewer) may read the texts and the outcome of its dossiers; for that person only
    the quotes count (M4: a viewer sees no quote).
    """
    archived = canary.archived
    docs = [
        r[0] for r in ops.query("SELECT id::text FROM document WHERE event_id = :e", e=archived)
    ]
    files = [
        r[0] for r in ops.query("SELECT id::text FROM attachment WHERE event_id = :e", e=archived)
    ]
    paths: list[tuple[str, dict[str, Any]]] = [
        (f"/api/archive/{archived}", {}),
        (f"/api/archive/{canary.live}", {}),
        ("/api/library", {"limit": 50}),
        ("/api/library", {"q": "CANARY"}),
        ("/api/templates", {"q": "CANARY"}),
        ("/api/templates", {"q": "Kinoabend"}),
        (f"/api/events/{archived}/clone-preview", {}),
        (f"/api/events/{archived}/last-time", {}),
        ("/api/formats/movienight", {}),
        ("/api/formats", {}),
    ]
    if foreign:
        paths += [
            (f"/api/events/{archived}", {}),
            (f"/api/events/{archived}/quotes", {}),
            (f"/api/events/{archived}/documents", {}),
            (f"/api/events/{archived}/comments", {}),
        ]
    paths += [
        ("/api/search", {"q": q, "scope": scope, "limit": 50})
        for scope in ("events", "documents", "formats")
        for q in ("CANARY", "CANARY-INTERNAL", "TEAMFILE", "DOCORG", "Kontext")
    ]
    paths += [(f"/api/documents/{d}", {}) for d in docs] if foreign else []
    paths += [(f"/api/attachments/{f}/download", {}) for f in files]
    responses = [client.get(path, params=params) for path, params in paths]
    markers = (INTERNAL, AMOUNT_DIGITS) if foreign else (f"{INTERNAL}QUOTE",)
    return leaks(responses, markers), len(responses)
