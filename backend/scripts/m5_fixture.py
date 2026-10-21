"""The Movienight stock of the M5 acceptance (`tests/fixtures/movienight.yaml`): 23 copies.

Eight archived copies (WS25/26), eight in follow-up (SoSe26) and seven live (WS26/27, two of
them the Halloween double of one Saturday), all of the format `movienight`. One archived copy
is the full one: poster, exception, two quote groups, a resolved comment, a checklist with
assignees, howto, note and mail template, retrospective and the outcome 87 / 245,00 EUR /
130,00 EUR. The live copies share one semester poster. Titles and numbers are invented. The
pipeline only lets a dossier start in the future, so the past copies are created ahead and
moved back by SQL on the dates (the clock moves, the state stays with the worker).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import yaml

from scripts import m3_worker as clock
from scripts import m4_acceptance as m4
from scripts.acceptance_common import check, confirm_location, expect, step
from tests._support.factories import png_bytes

STOCK = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "movienight.yaml"
OUTCOME = {"attendance": 87, "costsCents": 24500, "revenueCents": 13000, "notes": "Mehr Stühle."}
WEEKDAYS = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4}
BERLIN = ZoneInfo("Europe/Berlin")
SEMESTER_BASE = {"WS25/26": -300, "SoSe26": -150, "WS26/27": 12}


@dataclass
class Stock:
    """The ids of the stock by state; `full` is the fully equipped archived copy."""

    full: str = ""
    archived: list[str] = field(default_factory=list)
    followup: list[str] = field(default_factory=list)
    live: list[str] = field(default_factory=list)


def load() -> dict[str, Any]:
    """Read the stock definition."""
    return yaml.safe_load(STOCK.read_text(encoding="utf-8"))


def day_of(semester: str, weekday: str, index: int) -> datetime:
    """Return a start (20:00 local time) on the weekday, `index` weeks into the semester."""
    first = datetime.now(UTC).replace(hour=19, minute=0, second=0, microsecond=0)
    first += timedelta(days=SEMESTER_BASE[semester] + 7 * index)
    return first + timedelta(days=(WEEKDAYS[weekday] - first.weekday()) % 7)


def halloween(which: str) -> datetime:
    """Return the start of the Halloween double: 19:00 and 21:30 on the coming 31 October."""
    today = datetime.now(BERLIN).date()
    day = date(today.year, 10, 31)
    if day <= today:
        day = date(today.year + 1, 10, 31)
    hour, minute = (19, 0) if which == "first" else (21, 30)
    return datetime.combine(day, time(hour, minute), BERLIN).astimezone(UTC)


def create(organizer: httpx.Client, title: str, starts: datetime) -> str:
    """Create a dossier of the FSI in `idea` at `starts` (ahead of the clock, moved later)."""
    stamp = m4.stamp()
    ahead = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(days=14)
    body = {
        "title": f"{title} {stamp}",
        "startsAt": ahead.isoformat(),
        "endsAt": (ahead + timedelta(hours=3)).isoformat(),
        "organizationId": m4.ref_id(organizer, "/api/organizations", "fsi", creatable="true"),
        "venueText": "Kinosaal 9-133",
        "primaryCategoryId": m4.ref_id(organizer, "/api/categories", "kino"),
        "summary": "Der Filmabend im Kinosaal.",
    }
    eid = expect(organizer.post("/api/events", json=body), 201, f"stock: {title}")["id"]
    expect(
        organizer.put(
            f"/api/events/{eid}/format",
            json={"slug": "movienight"},
            headers=m4.etag(organizer, eid),
        ),
        200,
        "stock: format movienight",
    )
    return eid


def equip(organizer: httpx.Client, editor: httpx.Client, eid: str) -> None:
    """Give the full copy its quotes, comment, checklist, documents (before T02)."""
    for grp, vendor, cents in (("Technik", "Licht GmbH", 120_000), ("Catering", "Brot AG", 30_000)):
        expect(
            organizer.post(
                f"/api/events/{eid}/quotes",
                json={"grp": grp, "vendor": vendor, "amountCents": cents},
            ),
            201,
            f"stock: quote {vendor}",
        )
    comment = expect(
        editor.post(f"/api/events/{eid}/comments", json={"bodyMd": "Ist der Saal frei?"}),
        201,
        "stock: comment",
    )
    expect(editor.post(f"/api/comments/{comment['id']}/resolve"), 200, "stock: resolve")
    template = expect(
        organizer.post(f"/api/events/{eid}/checklist/apply-template", json={}),
        200,
        "stock: checklist",
    )
    for item in template["items"]:
        if item["phase"] in {"planning", "followup"}:
            expect(
                organizer.post(f"/api/checklist-items/{item['id']}/done", json={"done": True}),
                200,
                f"stock: done '{item['text']}'",
            )
    for kind, title, body in (
        ("howto", "Anleitung", "# Aufbau\n\nPopcornmaschine ausleihen."),
        ("notes", "Interne Notiz", "Der Hausmeister kommt um 17 Uhr."),
    ):
        expect(
            organizer.post(
                f"/api/events/{eid}/documents", json={"kind": kind, "title": title, "bodyMd": body}
            ),
            201,
            f"stock: {kind}",
        )
    expect(
        organizer.put(
            f"/api/events/{eid}/mail-templates/new",
            json={
                "title": "Einladung",
                "subject": "Einladung: {{ event.title }}",
                "bodyMd": "Hallo!",
                "visibility": "shared",
            },
        ),
        201,
        "stock: mail template",
    )


def poster_or_exception(
    organizer: httpx.Client, editor: httpx.Client, eid: str, *, semester_poster: bool
) -> None:
    """Upload the semester poster (1440 x 1800) or let the editor grant the exception."""
    if semester_poster:
        data = png_bytes(1440, 1800, "#335599")
        made = expect(
            m4.upload(organizer, eid, "semester.png", data, "poster", **m4.RIGHTS),
            201,
            "stock: poster",
        )
        m4.scanned(organizer, made["id"], eid)
        return
    expect(
        editor.post(
            f"/api/events/{eid}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, eid),
        ),
        200,
        "stock: image exception",
    )


def publish(organizer: httpx.Client, editor: httpx.Client, eid: str) -> None:
    """T01, T02, T04, T05 with the location confirmation T04 asks for."""
    for client, transition in (
        (organizer, "T01"),
        (organizer, "T02"),
        (editor, "T04"),
        (editor, "T05"),
    ):
        if transition == "T04":
            confirm_location(client, eid)
        expect(
            client.post(
                f"/api/events/{eid}/transitions/{transition}", json={}, headers=m4.etag(client, eid)
            ),
            200,
            f"stock: {transition}",
        )


def finish(organizer: httpx.Client, eid: str, outcome: dict[str, Any]) -> None:
    """Retrospective, outcome, verification and T09 (state followup).

    The format has a master howto, so every copy has a howto to verify (guard of T09).
    """
    expect(
        organizer.post(
            f"/api/events/{eid}/documents",
            json={"kind": "retrospective", "bodyMd": "Der Saal war voll."},
        ),
        201,
        "stock: retrospective",
    )
    expect(
        organizer.put(f"/api/events/{eid}/outcome", json=outcome, headers=m4.etag(organizer, eid)),
        200,
        "stock: outcome",
    )
    expect(organizer.post(f"/api/events/{eid}/actions/verify-howto"), 200, "stock: verify howto")
    expect(
        organizer.post(
            f"/api/events/{eid}/transitions/T09", json={}, headers=m4.etag(organizer, eid)
        ),
        200,
        "stock: T09",
    )


def build(organizer: httpx.Client, editor: httpx.Client) -> Stock:
    """Create the 23 copies; return their ids by state."""
    stock, spec = Stock(), load()
    per_semester: dict[str, int] = {}
    created: list[tuple[str, dict[str, Any], datetime]] = []
    for entry in spec["editions"]:
        index = per_semester.get(entry["semester"], 0)
        per_semester[entry["semester"]] = index + 1
        start = day_of(entry["semester"], entry["weekday"], index)
        if entry.get("halloween"):
            start = halloween(entry["halloween"])
        eid = create(organizer, entry["title"], start)
        if entry.get("full"):
            equip(organizer, editor, eid)
            poster_or_exception(organizer, editor, eid, semester_poster=False)
        poster_or_exception(
            organizer,
            editor,
            eid,
            semester_poster=entry["state"] == "live" or bool(entry.get("full")),
        )
        publish(organizer, editor, eid)
        created.append((eid, entry, start))
        step(f"stock: {entry['title']} -> live")
    for eid, entry, start in created:
        if entry["state"] == "live":
            clock.shift_dates(eid, starts_at=start, ends_at=start + timedelta(hours=3))
            stock.live.append(eid)
        else:
            clock.shift_dates(eid, starts_at=start, ends_at=start + timedelta(hours=3))
    line = clock.run_advance_once()
    check("followup=" in line, "stock: the worker moved the ended copies to followup")
    for eid, entry, _ in created:
        if entry["state"] == "archived":
            full = bool(entry.get("full"))
            finish(organizer, eid, OUTCOME if full else {"attendance": 40, "costsCents": 5000})
            stock.archived.append(eid)
            if full:
                stock.full = eid
        elif entry["state"] == "followup":
            stock.followup.append(eid)
    check(
        len(stock.archived) == 8 and len(stock.followup) == 8 and len(stock.live) == 7,
        "stock: 8 / 8 / 7",
    )
    return stock
