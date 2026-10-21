"""Items c to f of the M5 acceptance: calendars, canary, Schemathesis, the snapshot cache.

c: the golden files stay byte-equal (unit tests), every file and the dev calendars parse with
`icalendar` and pass the RFC 5545 rules of `m5_icsrules`; a cancellation shows
`STATUS:CANCELLED`, a postponement a higher `SEQUENCE`, the repeated hour of 25.10.2026 is
written in UTC. d: the canary (contract 10.1) is hung onto two dev dossiers and every public
and foreign-facing answer is scanned. e: Schemathesis runs against the dev API. f: a T05
yields a new snapshot; without Redis the feed and the calendars still answer from the view.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from icalendar import Calendar

from scripts import m4_acceptance as m4
from scripts import m4_ops as ops
from scripts.acceptance_common import check, expect, login, step
from scripts.m5_canary import foreign_requests, public_requests, seed
from scripts.m5_icsrules import problems
from scripts.m5_live import anonymous, live
from scripts.m5_schemathesis import run_schemathesis
from tests._support.canary import AMOUNT_DIGITS

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden" / "ics"
REDIS = ops.REDIS_CONTAINER
SECOND_0230 = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
FIRST_0230 = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def _vevents(body: bytes) -> dict[str, Any]:
    return {str(c["UID"]).split("@")[0]: c for c in Calendar.from_ical(body).walk("VEVENT")}


def _calendar(path: str) -> bytes:
    with anonymous() as client:
        response = client.get(path)
    check(response.status_code == 200, f"c: {path} -> 200")
    check(
        response.headers["content-type"].startswith("text/calendar"), f"c: {path} is text/calendar"
    )
    check("set-cookie" not in response.headers, f"c: {path} sets no cookie")
    found = problems(response.content)
    check(not found, f"c: {path} passes the RFC 5545 rules {found[:3]}")
    return response.content


def check_ics(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item c: goldens, parser, rules, cancellation, postponement and the October change."""
    unit = subprocess.run(
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", "tests/unit/publicapi/test_ics.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    check(
        unit.returncode == 0,
        f"c: golden and writer unit tests ({unit.stdout.strip().splitlines()[-1]})",
    )
    for golden in sorted(GOLDEN.glob("*.ics")):
        body = golden.read_bytes()
        Calendar.from_ical(body)
        check(not problems(body), f"c: golden {golden.name} parses and passes the rules")
    cancelled = live(organizer, editor, "M5 ICS Absage", days=33)
    postponed = live(organizer, editor, "M5 ICS Verschiebung", days=34)
    second = live(
        organizer,
        editor,
        "M5 Umstellung zweite",
        times=(SECOND_0230, SECOND_0230 + timedelta(minutes=15)),
    )
    first = live(
        organizer,
        editor,
        "M5 Umstellung erste",
        times=(FIRST_0230, FIRST_0230 + timedelta(minutes=15)),
    )
    before = _vevents(_calendar("/ics/all.ics"))
    expect(
        editor.post(
            f"/api/events/{cancelled}/actions/cancel",
            json={
                "reason": "Saal belegt",
                "publicReasonCode": "room",
                "publicReasonText": "Saal belegt",
            },
            headers=m4.etag(editor, cancelled),
        ),
        200,
        "c: cancel",
    )
    new_start = (datetime.now(UTC) + timedelta(days=41)).replace(minute=0, second=0, microsecond=0)
    expect(
        editor.post(
            f"/api/events/{postponed}/actions/postpone",
            json={
                "reason": "Referent:in krank",
                "publicReasonCode": "speaker",
                "newStartsAt": new_start.isoformat(),
                "newEndsAt": (new_start + timedelta(hours=3)).isoformat(),
            },
            headers=m4.etag(editor, postponed),
        ),
        200,
        "c: postpone",
    )
    after = _vevents(_calendar("/ics/all.ics"))
    kino = _vevents(_calendar("/ics/k/kino.ics"))
    gone = after[cancelled]
    check(str(gone["STATUS"]) == "CANCELLED", "c: the cancellation is STATUS:CANCELLED")
    check(gone["SEQUENCE"] > before[cancelled]["SEQUENCE"], "c: the cancellation raises SEQUENCE")
    moved = after[postponed]
    check(
        moved["SEQUENCE"] > before[postponed]["SEQUENCE"],
        f"c: the postponement raises SEQUENCE to {moved['SEQUENCE']}",
    )
    check(
        moved["DTSTART"].dt == new_start, f"c: DTSTART follows the new start {moved['DTSTART'].dt}"
    )
    check(str(moved["STATUS"]) == "TENTATIVE", "c: postponed is STATUS:TENTATIVE (D7)")
    check(set(after) == set(before), "c: UIDs stay stable")
    _october_change(second, first)
    check(cancelled in kino and postponed in kino, "c: both are in the category calendar kino")
    step(f"c: all.ics {len(after)} events, kino.ics {len(kino)} events")


def _october_change(second: str, first: str) -> None:
    with anonymous() as client:
        text = client.get("/ics/all.ics").text.replace("\r\n ", "")
    blocks = {b.split("UID:")[1].split("@")[0]: b for b in text.split("BEGIN:VEVENT")[1:]}
    check(
        "DTSTART:20261025T013000Z" in blocks[second],
        "c: 02:30 the second time is written in UTC (D8)",
    )
    check(
        "DTSTART:20261025T003000Z" in blocks[first],
        "c: 02:30 the first time is written in UTC too (ical.js reads TZID there as the second)",
    )


def check_canary(
    organizer: httpx.Client,
    editor: httpx.Client,
    member: httpx.Client,
    makers: httpx.Client,
    viewer: httpx.Client,
    archived: str,
) -> None:
    """Item d: no internal string and no amount reaches the public or a foreign reader."""
    canary = seed(organizer, editor, archived)
    try:
        with anonymous() as client:
            leaks, positive = public_requests(client)
        check(not leaks, f"d: anonymous feed and every calendar are clean {leaks[:3]}")
        check(positive, "d: the positive canary is found in feed and calendar")
        readers = (
            ("member", member),
            ("organizer-makers", makers),
            ("submitter-ekhg", login("submitter-ekhg")),
            ("viewer-fsi", viewer),
        )
        for name, client in readers:
            found, count = foreign_requests(client, canary, foreign=name != "viewer-fsi")
            check(not found, f"d: {name}: {count} answers without internal strings {found[:3]}")
        own = organizer.get(
            "/api/search", params={"q": "CANARY-INTERNAL-DOCORG", "scope": "documents"}
        )
        check(
            own.json()["total"] >= 1, "d: counter-check: organizer-fsi finds its own org document"
        )
        preview = organizer.get(f"/api/events/{canary.archived}/clone-preview").text
        check(
            "CANARY-INTERNAL-OUTCOMENOTES" in preview and AMOUNT_DIGITS in preview,
            "d: counter-check: the own clone preview shows notes and costs",
        )
    finally:
        ops.query("UPDATE organization SET contact_public = NULL WHERE slug = 'fsi'")


def check_schemathesis() -> None:
    """Item e: Schemathesis against the public operations of the dev API."""
    sent, failures = asyncio.run(run_schemathesis())
    check(not failures, f"e: Schemathesis {sent} cases, {len(failures)} failures {failures[:3]}")


def _redis(*args: str) -> str:
    return subprocess.run(
        ["docker", "exec", REDIS, "redis-cli", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _fresh_snapshot(timeout: int = 60) -> str:
    for _ in range(timeout):
        version = _redis("GET", "events:feed:version")
        if _redis("HGET", "events:public:snap:feed", "version") == version:
            return version
        time.sleep(1)
    check(False, "f: the worker rebuilt the snapshot in time")
    raise AssertionError


def _feed_paging(client: httpx.Client, since: datetime, eid: str) -> None:
    whole = [
        i["id"]
        for i in client.get("/api/public/feed/events", params={"limit": 500}).json()["items"]
    ]
    walked: list[str] = []
    cursor = None
    while True:
        page = client.get(
            "/api/public/feed/events",
            params={"limit": 10, **({"cursor": cursor} if cursor else {})},
        ).json()
        walked += [i["id"] for i in page["items"]]
        cursor = page.get("nextCursor")
        if not cursor:
            break
    check(walked == whole, f"f: the cursor walks all {len(whole)} items once, in order")
    changed = client.get(
        "/api/public/feed/events", params={"since": since.isoformat(), "limit": 500}
    )
    ids = [i["id"] for i in changed.json()["items"]]
    check(eid in ids and len(ids) < len(whole), f"f: since {since.isoformat()} -> {len(ids)} items")
    spaced = client.get(f"/api/public/feed/events?since={since.isoformat().replace('+', ' ')}")
    check(spaced.status_code == 400, "f: since with an unencoded plus -> 400")


def check_cache(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item f: T05 makes a new snapshot and ETag; without Redis the view answers."""
    with anonymous() as client:
        version = _fresh_snapshot()
        old = client.get("/api/public/feed/events", params={"limit": 500}).headers["etag"]
        expect(
            client.get(
                "/api/public/feed/events", params={"limit": 500}, headers={"If-None-Match": old}
            ),
            304,
            "f: 304 with the current ETag",
        )
        since = datetime.now(UTC).replace(microsecond=0)
        eid = live(organizer, editor, "M5 Cache", days=36)
        new_version = _fresh_snapshot()
        check(int(new_version) > int(version), f"f: feed version {version} -> {new_version}")
        page = client.get("/api/public/feed/events", params={"limit": 500})
        check(page.headers["etag"] != old, "f: a new ETag after T05")
        check(eid in page.text, "f: the new dossier is in the feed")
        stale = client.get(
            "/api/public/feed/events", params={"limit": 500}, headers={"If-None-Match": old}
        )
        check(stale.status_code == 200, "f: the old ETag no longer gives 304")
        _feed_paging(client, since, eid)
        built = _redis("HGET", "events:public:snap:feed", "generatedAt")
        served = client.get("/api/public/feed/events", params={"limit": 1}).json()["generatedAt"]
        check(
            datetime.fromisoformat(served) == datetime.fromisoformat(built),
            f"f: the feed answers from snapshot version {new_version} (generatedAt {built})",
        )
        ops.redis_down()
        try:
            for path in ("/api/public/feed/events", "/ics/all.ics", "/ics/k/kino.ics"):
                answer = client.get(path)
                check(answer.status_code == 200, f"f: without Redis {path} -> 200 from the view")
            check(
                eid in client.get("/api/public/feed/events", params={"limit": 500}).text,
                "f: live answer complete",
            )
        finally:
            ops.redis_up()
        client.get("/api/public/feed/events")
        expect(client.get("/api/public/feed/events"), 200, "f: feed after Redis is back")
        _fresh_snapshot()
        step("ok   f: the snapshot returns after Redis is back")
