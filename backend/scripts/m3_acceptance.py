"""M3 acceptance run against a host-run API and the dev stack (`python -m scripts.m3_acceptance`).

Criterion (PLAN 16.1, row M3, local reading): a trusted approver cannot approve the own
submission, an organizer corrects the summary in `live` while the time stays with the
editorial team, a cancellation stays in the feed as `cancelled`, an autosave draft survives
a reload while a stale base answers 409, and the worker publishes a scheduled dossier and
moves an ended one to `followup`. The script logs in through the real OIDC flow for each
person and works through the real API. Direct SQL only moves dates for the worker checks
(`scripts.m3_worker`) and proves that the database refuses `live` without an image.

The worker steps run `advance_states` once on the running worker instead of waiting for
the quarter-hour; `M3_WAIT_CRON=1` waits for the scheduled run instead (up to 17 minutes).

Only for the local stack. It needs the migrated and seeded database and a running worker.
"""

from __future__ import annotations

import io
import os
import time
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.settings import get_settings
from scripts import acceptance_common as common
from scripts.acceptance_common import API, check, expect, login, step
from scripts.keycloak_admin import Keycloak
from scripts.m3_worker import ended, run_advance_once, shift_dates

common.PREFIX[0] = "m3"
WORKER_WAIT_SECONDS = 17 * 60


def stamp() -> str:
    """Return a title suffix that keeps repeated runs apart."""
    return datetime.now(UTC).strftime("%H%M%S")


def org_id(client: httpx.Client, slug: str) -> str:
    """Return the id of an organization the person may create in."""
    orgs = expect(client.get("/api/organizations", params={"creatable": "true"}), 200, "orgs")
    return next(o["id"] for o in orgs if o["slug"] == slug)


def category_id(client: httpx.Client, slug: str = "kino") -> str:
    """Return the id of a category by slug."""
    cats = expect(client.get("/api/categories"), 200, "categories")
    return next(c["id"] for c in cats if c["slug"] == slug)


def create(client: httpx.Client, org: str, title: str, days: int = 20) -> dict:
    """Create a complete dossier in `idea`."""
    start = (datetime.now(UTC) + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    body = {
        "title": f"{title} {stamp()}",
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=3)).isoformat(),
        "organizationId": org_id(client, org),
        "venueText": "Kinosaal 9-133",
        "primaryCategoryId": category_id(client),
        "summary": "Ein Film, ein Saal, gute Laune.",
    }
    return expect(client.post("/api/events", json=body), 201, f"create '{body['title']}'")


def if_match(client: httpx.Client, eid: str) -> dict[str, str]:
    """The current version of the dossier as `If-Match` (T04, T05 and status actions need it)."""
    return {"If-Match": client.get(f"/api/events/{eid}").headers.get("etag", "")}


def fire(client: httpx.Client, eid: str, tid: str, status: int = 200, **body: object) -> dict:
    """Fire a transition and check the status."""
    return expect(
        client.post(
            f"/api/events/{eid}/transitions/{tid}", json=body, headers=if_match(client, eid)
        ),
        status,
        f"{tid} -> {status}",
    )


def png() -> bytes:
    """Return a valid PNG above the 1200 px poster minimum (M4 D6)."""
    buffer = io.BytesIO()
    Image.new("RGB", (1400, 900), "#3366cc").save(buffer, "PNG")
    return buffer.getvalue()


def upload_poster(client: httpx.Client, eid: str) -> None:
    """Upload a poster and wait until the worker scanned it and built the derivatives."""
    response = client.post(
        f"/api/events/{eid}/poster",
        data={"altText": "Ein Filmplakat", "credit": "Foto: Ada", "rightsBasis": "own_work"},
        files={"file": ("poster.png", png(), "image/png")},
    )
    expect(response, 201, "poster upload")
    for _ in range(60):
        poster = client.get(f"/api/events/{eid}").json()["poster"]
        if poster and poster["scanStatus"] == "clean" and poster["derivatives"]:
            step("ok   the worker scanned the poster and built the derivatives")
            return
        time.sleep(1)
    check(False, "the poster becomes clean with derivatives within a minute")


def grant_exception(editor: httpx.Client, eid: str) -> None:
    """Let the editor grant the image exception."""
    expect(
        editor.post(
            f"/api/events/{eid}/actions/image-exception", json={"reason": "Abnahme ohne Motiv"}
        ),
        200,
        "image exception",
    )


def feed_item(eid: str) -> dict | None:
    """Return the feed item of a dossier, or `None`."""
    items = httpx.get(f"{API}/api/public/feed/events", params={"limit": 500}).json()["items"]
    return next((i for i in items if i["id"] == eid), None)


def prepare_scheduled(organizer: httpx.Client, editor: httpx.Client) -> tuple[str, datetime]:
    """Bring a dossier with a poster to `approved` with `publishAt` two minutes ahead."""
    event = create(organizer, "fsi", "M3 Zeitplan")
    eid = event["id"]
    fire(organizer, eid, "T01")
    upload_poster(organizer, eid)
    fire(organizer, eid, "T02")
    when = datetime.now(UTC) + timedelta(minutes=2)
    approved = fire(editor, eid, "T04", publishAt=when.isoformat())
    check(approved["state"] == "approved" and approved["publishAt"], "i: T04 with publishAt")
    return eid, when


def four_eyes(approver: httpx.Client, second: httpx.Client, editor: httpx.Client) -> None:
    """b: the trusted approver cannot approve the own submission."""
    event = create(approver, "stupa", "M3 Vier-Augen")
    eid = event["id"]
    fire(approver, eid, "T01")
    grant_exception(editor, eid)
    fire(approver, eid, "T02")
    refused = fire(approver, eid, "T04", 403)
    check(refused["code"] == "four_eyes", "b: approver-stupa gets 403 four_eyes on the own dossier")
    fire(second, eid, "T04")
    live = fire(second, eid, "T05")
    check(live["state"] == "live", "b: approver2-stupa approves and publishes")


def field_classes(organizer: httpx.Client, editor: httpx.Client) -> str:
    """c, d, e: editor approves, organizer and editor change fields, cancel stays in the feed."""
    event = create(organizer, "fsi", "M3 Feldklassen")
    eid = event["id"]
    fire(organizer, eid, "T01")
    upload_poster(organizer, eid)
    fire(organizer, eid, "T02")
    fire(editor, eid, "T04")
    live = fire(editor, eid, "T05")
    check(live["state"] == "live", "c: the editor approved and published the fsi dossier")
    headers = {"If-Match": f'"{live["rev"]}"'}
    summary = expect(
        organizer.patch(f"/api/events/{eid}", json={"summary": "Neuer Kurztext"}, headers=headers),
        200,
        "d: organizer corrects the summary in live",
    )
    moved = (datetime.fromisoformat(live["startsAt"]) + timedelta(days=1)).isoformat()
    locked = expect(
        organizer.patch(
            f"/api/events/{eid}",
            json={"startsAt": moved, "endsAt": moved},
            headers={"If-Match": f'"{summary["rev"]}"'},
        ),
        409,
        "d: organizer cannot move the time",
    )
    check(locked["code"] == "field_locked", "d: the answer is field_locked")
    later = datetime.fromisoformat(live["endsAt"]) + timedelta(days=1)
    expect(
        editor.patch(
            f"/api/events/{eid}",
            json={"startsAt": moved, "endsAt": later.isoformat()},
            headers={"If-Match": f'"{summary["rev"]}"'},
        ),
        200,
        "d: the editor moves the time",
    )
    expect(
        organizer.post(
            f"/api/events/{eid}/actions/cancel",
            json={"reason": "Referent krank", "publicReasonCode": "illness"},
            headers=if_match(organizer, eid),
        ),
        200,
        "e: organizer cancels",
    )
    item = feed_item(eid)
    check(item is not None and item["status"] == "cancelled", "e: the feed shows 'cancelled'")
    back = expect(
        editor.post(
            f"/api/events/{eid}/actions/reinstate",
            json={"reason": "Doch"},
            headers=if_match(editor, eid),
        ),
        200,
        "e: undo",
    )
    check(
        back["state"] == "live" and back["publicStatus"] == "scheduled",
        "e: reinstate keeps live and sets the public status back to scheduled",
    )
    item = feed_item(eid)
    check(item is not None and item["status"] == "scheduled", "e: the feed shows 'scheduled'")
    return eid


def proposals(member: httpx.Client) -> None:
    """f: five open proposals at most; the extra attempt is a 422."""
    made = []
    for n in range(6):
        body = {"title": f"M3 Vorschlag {n} {stamp()}", "startsAt": "2031-01-01T10:00:00Z"}
        response = member.post("/api/events", json=body)
        if response.status_code == 422:
            check(
                response.json()["code"] == "proposal_quota_exceeded",
                "f: the extra proposal is proposal_quota_exceeded",
            )
            break
        made.append(expect(response, 201, "f: proposal")["id"])
    else:
        check(False, "f: the quota stops the sixth open proposal")
    for eid in made:
        fire(member, eid, "T11", note="Abnahme aufgeräumt")


def autosave(organizer: httpx.Client) -> None:
    """g: draft, reload, PATCH clears it."""
    event = create(organizer, "fsi", "M3 Autosave")
    eid, rev = event["id"], event["rev"]
    fields = {"summary": "Halb getippt"}
    put = organizer.put(
        f"/api/events/{eid}/draft", json={"fields": fields}, headers={"If-Match": f'"{rev}"'}
    )
    expect(put, 200, "g: PUT draft")
    again = expect(organizer.get(f"/api/events/{eid}/draft"), 200, "g: GET draft after reload")
    check(again["fields"] == fields and again["baseRev"] == rev, "g: the draft is intact")
    saved = expect(
        organizer.patch(
            f"/api/events/{eid}", json={"summary": "Gespeichert"}, headers={"If-Match": f'"{rev}"'}
        ),
        200,
        "g: PATCH",
    )
    check(
        organizer.get(f"/api/events/{eid}/draft").status_code == 204, "g: PATCH cleared the draft"
    )
    stale = {"If-Match": f'"{rev}"'}
    late = expect(
        organizer.put(f"/api/events/{eid}/draft", json={"fields": fields}, headers=stale),
        409,
        "g: PUT draft on a stale base",
    )
    check(
        late["code"] == "conflict" and late["current"]["rev"] == saved["rev"],
        "g: the stale draft is a conflict carrying the current version",
    )
    clash = expect(
        organizer.patch(f"/api/events/{eid}", json={"summary": "Alt"}, headers=stale),
        409,
        "g: PATCH on a stale base",
    )
    check(
        clash["code"] == "conflict" and clash["current"]["summary"] == "Gespeichert",
        "g: the stale PATCH is a conflict and changes nothing",
    )


def notes(organizer: httpx.Client, editor: httpx.Client) -> None:
    """h: the notes of T03, T06, T07 and the withdrawal T11 / T12."""
    event = create(organizer, "fsi", "M3 Notizen")
    eid = event["id"]
    fire(organizer, eid, "T01")
    grant_exception(editor, eid)
    fire(organizer, eid, "T02")
    missing = fire(editor, eid, "T03", 422)
    check(missing["code"] == "reason_required", "h: T03 without a note is reason_required")
    # Since M4 T03 needs an open question; the dialog writes it first (M4 contract 4.2).
    question = {"bodyMd": "Bitte Ort prüfen"}
    expect(editor.post(f"/api/events/{eid}/comments", json=question), 201, "h: question")
    fire(editor, eid, "T03", note="Bitte Ort prüfen")
    fire(organizer, eid, "T02")
    fire(editor, eid, "T04")
    fire(editor, eid, "T06", note="Doch noch ändern")
    fire(editor, eid, "T04")
    fire(editor, eid, "T05")
    check(fire(editor, eid, "T07", note="Fehler im Text")["state"] == "approved", "h: T07")
    idea = create(organizer, "fsi", "M3 Verwerfen")
    fire(organizer, idea["id"], "T11", note="Entfällt")
    check(fire(editor, idea["id"], "T12")["state"] == "idea", "h: the editor restores with T12")


def database_net(organizer: httpx.Client) -> None:
    """j: direct SQL cannot publish without an image."""
    event = create(organizer, "fsi", "M3 Netz")
    fire(organizer, event["id"], "T01")
    fire(organizer, event["id"], "T02")
    engine = create_engine(get_settings().database_url.replace("+asyncpg", "+psycopg"))
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE event SET state = 'live' WHERE id = :i"), {"i": event["id"]})
        check(False, "j: the database refuses live without an image")
    except DBAPIError as error:
        sqlstate = getattr(error.orig, "sqlstate", None)
        check(sqlstate == "23514", f"j: UPDATE state='live' without an image fails with {sqlstate}")
    finally:
        engine.dispose()


def wait_for_worker(eid: str, when: datetime) -> None:
    """i: the scheduled dossier goes live on the worker run after `publishAt`."""
    if os.environ.get("M3_WAIT_CRON") != "1":
        time.sleep(max(0.0, (when - datetime.now(UTC)).total_seconds()) + 1)
        line = run_advance_once()
        check("failed=0" in line, "i: the manual advance_states run has no failure")
    else:
        step(f"i: waiting for the next worker run after {when:%H:%M:%S} (up to 17 minutes)")
    deadline = time.monotonic() + WORKER_WAIT_SECONDS
    while time.monotonic() < deadline:
        organizer = login("organizer-fsi")
        state = expect(organizer.get(f"/api/events/{eid}"), 200, "i: read the dossier")["state"]
        if state == "live":
            check(feed_item(eid) is not None, "i: the worker published it, it is in the feed")
            return
        time.sleep(30)
    check(False, "i: the worker published the dossier within 17 minutes")


def worker_clock(organizer: httpx.Client, editor: httpx.Client) -> None:
    """k, l: publish_at moved into the past goes live; an end 13 hours ago goes to followup."""
    event = create(organizer, "fsi", "M3 Uhr")
    eid = event["id"]
    fire(organizer, eid, "T01")
    upload_poster(organizer, eid)
    fire(organizer, eid, "T02")
    later = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    check(fire(editor, eid, "T04", publishAt=later)["state"] == "approved", "k: T04 for tomorrow")
    shift_dates(eid, publish_at=datetime.now(UTC) - timedelta(minutes=1))
    line = run_advance_once()
    check("published=0" not in line and "failed=0" in line, "k: the run reports a publication")
    live = expect(editor.get(f"/api/events/{eid}"), 200, "k: read the dossier")
    check(live["state"] == "live", "k: the worker set the overdue dossier live")
    check(feed_item(eid) is not None, "k: the dossier is in the feed")
    shift_dates(eid, **ended(13))
    line = run_advance_once()
    check("followup=0" not in line and "failed=0" in line, "l: the run reports a followup")
    done = expect(editor.get(f"/api/events/{eid}"), 200, "l: read the dossier")
    check(done["state"] == "followup", "l: an event that ended 13 hours ago is in followup")


def main() -> None:
    """Run the whole acceptance walk."""
    check(API.startswith(("http://localhost", "http://127.0.0.1")), f"API {API} is local")
    step(f"realm sync created {Keycloak().sync_realm_users()} missing group(s) or user(s)")
    organizer, editor, member = login("organizer-fsi"), login("editor"), login("member")
    approver, second = login("approver-stupa"), login("approver2-stupa")
    scheduled, when = prepare_scheduled(organizer, editor)
    four_eyes(approver, second, editor)
    field_classes(organizer, editor)
    proposals(member)
    autosave(organizer)
    notes(organizer, editor)
    database_net(organizer)
    wait_for_worker(scheduled, when)
    worker_clock(organizer, editor)
    step("M3 acceptance: all checks passed")


if __name__ == "__main__":
    main()
