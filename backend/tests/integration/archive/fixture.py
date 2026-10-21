"""A fully archived Movienight edition, built through the real API (the M5 acceptance fixture).

The edition has a poster and an image exception, two quote groups with amounts, a resolved
comment, a checklist with assignees, a howto, a note and a mail template, a retrospective and
the outcome 87 / 245,00 EUR / 130,00 EUR. It is archived through T09 and then moved into the
past, because the pipeline only lets a dossier start in the future.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from tests._support import samples
from tests.integration.dossier.helpers import clean_poster, upload
from tests.integration.events.harness import Api, future
from worker.advance import advance_states

OUTCOME = {"attendance": 87, "costsCents": 24500, "revenueCents": 13000, "notes": "Mehr Stühle."}


async def ok(response: Any, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def add_documents(api: Api, eid: str) -> None:
    for kind, title, visibility, body in (
        ("howto", "Anleitung", "shared", "# Aufbau\n\nPopcornmaschine ausleihen."),
        ("notes", "Interne Notiz", "org", "Der Hausmeister kommt um 17 Uhr."),
        ("mail_template", "Einladung", "shared", "Hallo {{ event.title }}"),
    ):
        await api.sql(
            "INSERT INTO document (event_id, kind, title, body_md, visibility, meta) "
            "VALUES (:e, :k, :t, :b, :v, CAST(:m AS jsonb))",
            e=eid,
            k=kind,
            t=title,
            b=body,
            v=visibility,
            m='{"subject": "Einladung"}' if kind == "mail_template" else "{}",
        )


async def add_quotes_and_comment(api: Api, eid: str) -> None:
    for grp, vendor, amount in (("Technik", "Licht GmbH", 120_000), ("Catering", "Brot", 30_000)):
        await ok(
            await api.request(
                "organizer-fsi",
                "POST",
                f"/api/events/{eid}/quotes",
                json={"grp": grp, "vendor": vendor, "amountCents": amount},
            ),
            201,
        )
    comment = await ok(
        await api.request(
            "editor", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "Ist der Saal frei?"}
        ),
        201,
    )
    await ok(await api.request("editor", "POST", f"/api/comments/{comment['id']}/resolve"))


async def done_required_items(api: Api, eid: str, phase: str) -> None:
    await api.sql(
        "UPDATE checklist_item SET done_at = now(), done_by = 'sub-org-fsi', "
        "assignee_sub = 'sub-org-fsi' WHERE event_id = :e AND phase = :p",
        e=eid,
        p=phase,
    )


async def add_files(api: Api, eid: str, files: Sequence[tuple[str, str, bool]]) -> list[str]:
    """Upload `(kind, visibility, scanned)` files of the sample PDF; return their ids."""
    ids = []
    for kind, visibility, scanned in files:
        out = await upload(
            api, "organizer-fsi", eid, kind, "plan.pdf", samples.pdf_bytes(), visibility=visibility
        )
        assert out.status_code == 201, out.text
        if scanned:
            assert await api.process_poster(out.json()["id"]) == "clean"
        ids.append(out.json()["id"])
    return ids


async def archived_movienight(
    api: Api,
    title: str = "Movienight: Whiplash",
    days_ago: int = 60,
    start_days: int = 10,
    files: Sequence[tuple[str, str, bool]] = (),
) -> str:
    """Build and archive one edition of the format `movienight`; return the dossier id.

    `files` are extra attachments `(kind, visibility, scanned)`, uploaded before the archive
    closes the dossier; look them up by SQL (`kind = 'other'` or `'quote'`).
    """
    event = await api.create_event(
        title=title,
        startsAt=future(start_days).isoformat(),
        endsAt=future(start_days, 3).isoformat(),
        costText="Eintritt frei",
        descriptionMd="Ein Film im Kinosaal.",
    )
    eid = event["id"]
    await ok(
        await api.request(
            "organizer-fsi",
            "PUT",
            f"/api/events/{eid}/format",
            json={"slug": "movienight"},
            headers={"If-Match": f'"{event["rev"]}"'},
        )
    )
    await ok(await api.fire("organizer-fsi", eid, "T01"))
    await ok(
        await api.request(
            "organizer-fsi", "POST", f"/api/events/{eid}/checklist/apply-template", json={}
        )
    )
    await add_documents(api, eid)
    await add_quotes_and_comment(api, eid)
    await clean_poster(api, eid)
    await add_files(api, eid, files)
    await done_required_items(api, eid, "planning")
    await ok(await api.fire("organizer-fsi", eid, "T02"))
    await ok(await api.fire("editor", eid, "T04"))
    await ok(await api.fire("editor", eid, "T05"))
    ended = datetime.fromisoformat((await api.get("editor", eid))["endsAt"])
    await advance_states(
        {"advance_sessionmaker": api.maker, "redis": api.pool}, now=ended + timedelta(hours=13)
    )
    await done_required_items(api, eid, "followup")
    await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "retrospective", "bodyMd": "Der Saal war voll."},
        ),
        201,
    )
    rev = (await api.get("organizer-fsi", eid))["rev"]
    await ok(
        await api.request(
            "organizer-fsi",
            "PUT",
            f"/api/events/{eid}/outcome",
            json=OUTCOME,
            headers={"If-Match": f'"{rev}"'},
        )
    )
    await ok(await api.request("organizer-fsi", "POST", f"/api/events/{eid}/actions/verify-howto"))
    await ok(await api.fire("organizer-fsi", eid, "T09"))
    await api.sql(
        "UPDATE event SET starts_at = starts_at - make_interval(days => CAST(:d AS int)), "
        "ends_at = ends_at - make_interval(days => CAST(:d AS int)) WHERE id = :e",
        d=days_ago + start_days,
        e=eid,
    )
    return eid
