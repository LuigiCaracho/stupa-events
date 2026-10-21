"""Item a of the M5 acceptance: a clone of the full Movienight copy, own and foreign.

The FSI clones its archived edition: a dossier in `idea` without poster, exception, quotes,
files and comments, the checklist open and due again from the new start, notes and mail
template copied as revision 1, the howto as a link to the format, and "last time" with
attendance and costs. MAKERS clones the same template and sees attendance only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from app.modules.dossier.checklist_due import due_at_for
from scripts.acceptance_common import check, expect, step
from scripts.m5_fixture import Stock

SAMPLE_OFFSETS = (-28, -7, 7)


def _start(days: int = 45) -> datetime:
    return (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )


def master_howto(editor: httpx.Client, source: str) -> None:
    """Make the howto of the full copy the master howto of the format (once)."""
    made = editor.post("/api/formats/movienight/howto", json={"fromEventId": source})
    check(made.status_code in {201, 409}, f"a: master howto of the format ({made.status_code})")


def _clone(client: httpx.Client, source: str, start: datetime) -> dict:
    return expect(
        client.post(f"/api/events/{source}/clone", json={"startsAt": start.isoformat()}),
        201,
        "a: clone",
    )


def _lists(client: httpx.Client, eid: str) -> tuple[dict, list, list, dict, dict]:
    quotes = expect(client.get(f"/api/events/{eid}/quotes"), 200, "a: quotes of the clone")
    files = expect(client.get(f"/api/events/{eid}/attachments"), 200, "a: files of the clone")
    comments = expect(client.get(f"/api/events/{eid}/comments"), 200, "a: comments of the clone")
    checklist = expect(client.get(f"/api/events/{eid}/checklist"), 200, "a: checklist")
    docs = {d["kind"]: d for d in expect(client.get(f"/api/events/{eid}/documents"), 200, "docs")}
    return quotes, files, comments, checklist, docs


def own_clone(organizer: httpx.Client, source: str) -> str:
    """Clone as the FSI and check every line of the carry-over table that the stock covers."""
    preview = expect(organizer.get(f"/api/events/{source}/clone-preview"), 200, "a: preview (FSI)")
    start = _start()
    made = _clone(organizer, source, start)
    event, report = made["event"], made["report"]
    check(report == preview["report"], "a: the preview equals the report")
    check(event["state"] == "idea" and event["derivedFromId"] == source, "a: idea, derivedFromId")
    check(event["poster"] is None and event["imageException"] is None, "a: no poster, no exception")
    eid = event["id"]
    quotes, files, comments, checklist, docs = _lists(organizer, eid)
    check(quotes["groups"] == [] and files == [] and comments == [], "a: no quotes/files/comments")
    items = checklist["items"]
    check(bool(items), f"a: checklist copied ({len(items)} items)")
    check(
        all(i["doneAt"] is None and i["assigneeSub"] is None for i in items),
        "a: all items open, no assignees",
    )
    dated = [i for i in items if i["dueOffsetDays"] is not None]
    check(event["checklistRecomputed"] == len(dated), f"a: checklistRecomputed = {len(dated)}")
    for offset in SAMPLE_OFFSETS:
        item = next((i for i in dated if i["dueOffsetDays"] == offset), None)
        check(item is not None, f"a: an item at {offset:+d} days")
        assert item is not None
        want = due_at_for(start, event["tzid"], offset)
        got = datetime.fromisoformat(item["dueAt"])
        check(got == want, f"a: '{item['text']}' due {got.isoformat()} ({offset:+d} days)")
    check({"notes", "mail_template"} <= set(docs), f"a: notes and mail template copied {set(docs)}")
    check("howto" not in docs, "a: no howto copy in the dossier")
    for kind in ("notes", "mail_template"):
        check(docs[kind]["rev"] == 1, f"a: {kind} at revision 1")
    howto = next(line for line in report if line["part"] == "howto")
    check(howto["mode"] == "link", "a: the howto is a link to the format")
    last = expect(organizer.get(f"/api/events/{eid}/last-time"), 200, "a: last time (FSI)")
    check(
        last["attendance"] == 87 and last["costsCents"] == 24500 and not last["restricted"],
        "a: last time shows 87 visitors and 245,00 EUR costs",
    )
    expect(organizer.get(f"/api/events/{source}/quotes"), 200, "a: quotes panel of the source")
    step(f"a: report {[(line['part'], line['mode'], line['count']) for line in report]}")
    return eid


def foreign_clone(makers: httpx.Client, source: str, live_of_fsi: str) -> None:
    """Clone as MAKERS: attendance without costs, only shared documents, panels 404."""
    made = _clone(makers, source, _start(50))
    event = made["event"]
    check(event["organization"]["slug"] == "makers", "a: the clone belongs to MAKERS")
    docs = {d["kind"] for d in expect(makers.get(f"/api/events/{event['id']}/documents"), 200, "")}
    check(docs <= {"mail_template"}, f"a: only shared documents copied ({docs})")
    last = expect(makers.get(f"/api/events/{event['id']}/last-time"), 200, "a: last time (MAKERS)")
    check(
        last["attendance"] == 87
        and last["costsCents"] is None
        and last["revenueCents"] is None
        and last["restricted"] is True,
        "a: last time with visitors, without costs, restricted",
    )
    expect(makers.get(f"/api/events/{source}/quotes"), 404, "a: quotes panel for MAKERS")
    refused = makers.post(
        f"/api/events/{live_of_fsi}/clone", json={"startsAt": _start(50).isoformat()}
    )
    check(refused.status_code == 404, f"a: a foreign live edition -> 404 ({refused.status_code})")


def check_clone(
    organizer: httpx.Client, editor: httpx.Client, makers: httpx.Client, stock: Stock
) -> None:
    """Run item a."""
    master_howto(editor, stock.full)
    own_clone(organizer, stock.full)
    foreign_clone(makers, stock.full, stock.live[0])
