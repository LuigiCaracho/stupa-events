"""Items h to k of the M5 acceptance: calendar view, archive reading, location and frame, PLAN 4.6.

h: `view=calendar` for October 2026 with its edge days, a multi-day entry, the Halloween
double of the stock, an all-day entry, 101 days refused, foreign dossiers unseen. i: a
person of another organization reads the core data and the shared parts of an archived
dossier, never `org` files or pending ones, and `adopt` copies text only. j: free venue text
blocks T04 until confirmed; a party needs its age limit; an all-day event reaches feed and
ICS as dates. k: search, clone, poster, T01, T02, question and T03, replacement, T02, T04,
T05, then the entry is in feed and ICS.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx

from scripts import m3_worker as clock
from scripts import m4_acceptance as m4
from scripts import m4_ops as ops
from scripts.acceptance_common import check, confirm_location, expect, step
from scripts.m5_fixture import Stock
from scripts.m5_live import anonymous
from tests._support.samples import pdf_bytes

OCTOBER = {"view": "calendar", "from": "2026-09-28", "to": "2026-11-08"}


def _create(client: httpx.Client, org: str, **body: object) -> dict:
    payload = {
        "title": f"{body.pop('title')} {m4.stamp()}",
        "organizationId": m4.ref_id(client, "/api/organizations", org, creatable="true"),
        "venueText": "Kinosaal 9-133",
        **body,
    }
    return expect(client.post("/api/events", json=payload), 201, f"create '{payload['title']}'")


def _entries(client: httpx.Client, params: dict[str, str]) -> dict[str, dict]:
    body = expect(
        client.get("/api/events", params=params),
        200,
        f"h: calendar {params['from']}..{params['to']}",
    )
    return {e["id"]: e for e in body["entries"]}


def check_calendar(
    organizer: httpx.Client, editor: httpx.Client, makers: httpx.Client, stock: Stock
) -> None:
    """Item h."""
    multi = _create(
        organizer,
        "fsi",
        title="M5 Mehrtägig",
        startsAt="2026-10-30T16:00:00Z",
        endsAt="2026-11-01T11:00:00Z",
    )
    whole = _create(organizer, "fsi", title="M5 Ganztägig", allDay=True, startsOn="2026-10-29")
    edge = _create(
        organizer,
        "fsi",
        title="M5 Randtag",
        startsAt="2026-11-07T18:00:00Z",
        endsAt="2026-11-07T21:00:00Z",
    )
    found = _entries(organizer, OCTOBER)
    check(
        all(e["id"] in found for e in (multi, whole, edge)),
        f"h: {len(found)} entries, own new ones inside",
    )
    check(
        found[multi["id"]]["endsAt"].startswith("2026-11-01"),
        "h: the multi-day entry spans into November",
    )
    check(found[whole["id"]]["allDay"] is True, "h: the all-day entry is marked all-day")
    halloween = [
        e
        for e in found.values()
        if e["id"] in stock.live and e["startsAt"].startswith("2026-10-31")
    ]
    check(
        len(halloween) == 2,
        f"h: the Halloween double on 31.10. ({[e['title'] for e in halloween]})",
    )
    too_long = organizer.get(
        "/api/events", params={"view": "calendar", "from": "2026-10-01", "to": "2027-01-09"}
    )
    check(
        too_long.status_code == 422 and too_long.json()["code"] == "range_too_large",
        "h: 101 days -> 422",
    )
    hundred = organizer.get(
        "/api/events", params={"view": "calendar", "from": "2026-10-01", "to": "2027-01-08"}
    )
    check(hundred.status_code == 200, "h: 100 days -> 200")
    foreign = _entries(makers, OCTOBER)
    check(
        multi["id"] not in foreign and whole["id"] not in foreign,
        "h: MAKERS does not see the FSI dossiers",
    )
    check(multi["id"] in _entries(editor, OCTOBER), "h: the editor sees them")


def _archived_with_files(
    organizer: httpx.Client, editor: httpx.Client
) -> tuple[str, dict[str, str]]:
    eid = m4.create(organizer, "M5 Archiv mit Dateien", days=38)
    files = {}
    for name, visibility in (("shared", "shared"), ("org", "org"), ("pending", "shared")):
        made = expect(
            organizer.post(
                f"/api/events/{eid}/attachments",
                data={"kind": "other", "visibility": visibility},
                files={"file": (f"{name}.pdf", pdf_bytes(), "application/pdf")},
            ),
            201,
            f"i: upload {name}",
        )
        m4.scanned(organizer, made["id"], eid)
        files[name] = made["id"]
    for kind, visibility in (("notes", "shared"), ("howto", "org")):
        expect(
            organizer.post(
                f"/api/events/{eid}/documents",
                json={
                    "kind": kind,
                    "title": f"M5 {visibility}",
                    "bodyMd": f"Text {visibility}",
                    "visibility": visibility,
                },
            ),
            201,
            f"i: document {visibility}",
        )
    expect(
        editor.post(
            f"/api/events/{eid}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, eid),
        ),
        200,
        "i: image exception",
    )
    m4.fire(organizer, eid, "T02")
    m4.fire(editor, eid, "T04")
    m4.fire(editor, eid, "T05")
    clock.shift_dates(eid, **clock.ended(13))
    clock.run_advance_once()
    expect(
        organizer.post(
            f"/api/events/{eid}/documents", json={"kind": "retrospective", "bodyMd": "ok"}
        ),
        201,
        "i: retrospective",
    )
    expect(
        organizer.put(
            f"/api/events/{eid}/outcome",
            json={"attendance": 20, "costsCents": 0},
            headers=m4.etag(organizer, eid),
        ),
        200,
        "i: outcome",
    )
    expect(organizer.post(f"/api/events/{eid}/actions/verify-howto"), 200, "i: verify howto")
    m4.fire(organizer, eid, "T09")
    ops.query("UPDATE attachment SET scan_status = 'pending' WHERE id = :i", i=files["pending"])
    return eid, files


def check_archive_reading(
    organizer: httpx.Client, editor: httpx.Client, member: httpx.Client, makers: httpx.Client
) -> None:
    """Item i."""
    eid, files = _archived_with_files(organizer, editor)
    seen = expect(member.get(f"/api/archive/{eid}"), 200, "i: member reads the archived dossier")
    kinds = {(d["kind"], d["visibility"]) for d in seen["documents"]}
    check(
        ("notes", "shared") in kinds and not any(v in {"org", "team"} for _, v in kinds),
        f"i: only shared documents {kinds}",
    )
    listed = {a["id"] for a in seen["attachments"]}
    check(listed == {files["shared"]}, "i: only the clean shared file is listed")
    m4.raw(
        member.get(f"/api/attachments/{files['shared']}/download"), 200, "i: foreign shared file"
    )
    m4.raw(member.get(f"/api/attachments/{files['org']}/download"), 404, "i: foreign org file")
    pending = member.get(f"/api/attachments/{files['pending']}/download").status_code
    check(pending in {404, 409}, f"i: pending shared file not reachable ({pending})")
    library = expect(
        member.get("/api/library", params={"q": "M5 Archiv mit Dateien", "limit": 100}),
        200,
        "i: library",
    )
    titles = str(library)
    check(
        files["org"] not in titles and files["pending"] not in titles,
        "i: library without org and pending files",
    )
    doc = next(d for d in seen["documents"] if d["kind"] == "notes")
    target = _create(
        makers,
        "makers",
        title="M5 Übernahme",
        startsAt=(datetime.now(UTC) + timedelta(days=50)).isoformat(),
    )
    adopted = expect(
        makers.post(f"/api/library/documents/{doc['id']}/adopt", json={"eventId": target["id"]}),
        201,
        "i: adopt",
    )
    check(adopted["bodyMd"] == "Text shared", "i: adopt copies the text")
    check(
        expect(makers.get(f"/api/events/{target['id']}/attachments"), 200, "i: files of the target")
        == [],
        "i: adopt copies no file",
    )
    refused = member.post(
        f"/api/library/documents/{doc['id']}/adopt", json={"eventId": target["id"]}
    )
    check(refused.status_code in {403, 404}, f"i: member may not adopt ({refused.status_code})")


def check_frame(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item j."""
    eid = m4.create(organizer, "M5 Ort", days=42)
    expect(
        editor.post(
            f"/api/events/{eid}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, eid),
        ),
        200,
        "j: exception",
    )
    m4.fire(organizer, eid, "T02")
    blocked = editor.post(
        f"/api/events/{eid}/transitions/T04", json={}, headers=m4.etag(editor, eid)
    )
    check(
        blocked.status_code == 422 and blocked.json()["code"] == "location_unconfirmed",
        "j: T04 -> 422 location_unconfirmed",
    )
    expect(
        editor.post(f"/api/events/{eid}/actions/confirm-location", json={"precision": "building"}),
        200,
        "j: confirm-location",
    )
    m4.fire(editor, eid, "T04")
    m4.fire(editor, eid, "T05")
    with anonymous() as client:
        item = next(
            i
            for i in client.get("/api/public/feed/events", params={"limit": 500}).json()["items"]
            if i["id"] == eid
        )
    check(item["venueText"] == "Kinosaal 9-133", "j: the feed shows the confirmed place")
    party = m4.create(organizer, "M5 Party", category="party", days=43)
    expect(
        editor.post(
            f"/api/events/{party}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, party),
        ),
        200,
        "j: exception",
    )
    refused = organizer.post(
        f"/api/events/{party}/transitions/T02", json={}, headers=m4.etag(organizer, party)
    )
    check(
        refused.status_code == 422 and "facts_invalid" in m4.reasons(refused),
        "j: a party without ageLimit blocks T02",
    )
    expect(
        organizer.put(
            f"/api/events/{party}/facts", json={"ageLimit": 18}, headers=m4.etag(organizer, party)
        ),
        200,
        "j: facts ageLimit 18",
    )
    allowed = organizer.get(f"/api/events/{party}/guards/T02").json()
    check("facts_invalid" not in str(allowed), "j: with ageLimit the facts no longer block")
    day = (date.today() + timedelta(days=44)).isoformat()
    whole = _create(
        organizer,
        "fsi",
        title="M5 Tag der offenen Tür",
        allDay=True,
        startsOn=day,
        summary="Ein Tag auf dem Campus.",
        primaryCategoryId=m4.ref_id(organizer, "/api/categories", "kino"),
    )
    m4.fire(organizer, whole["id"], "T01")
    expect(
        editor.post(
            f"/api/events/{whole['id']}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, whole["id"]),
        ),
        200,
        "j: exception",
    )
    m4.fire(organizer, whole["id"], "T02")
    m4.fire(editor, whole["id"], "T04")
    m4.fire(editor, whole["id"], "T05")
    with anonymous() as client:
        feed = client.get("/api/public/feed/events", params={"limit": 500}).json()["items"]
        item = next(i for i in feed if i["id"] == whole["id"])
        ics = client.get("/ics/all.ics").text.replace("\r\n ", "")
    check(
        item["startsOn"] == day and item["endsOn"] == day, f"j: the feed has startsOn/endsOn {day}"
    )
    block = next(b for b in ics.split("BEGIN:VEVENT") if whole["id"] in b)
    check(
        f"DTSTART;VALUE=DATE:{day.replace('-', '')}" in block, "j: the ICS has DTSTART;VALUE=DATE"
    )


def check_sequence(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item k: PLAN 4.6 from the search to feed and ICS."""
    hits = expect(organizer.get("/api/search", params={"q": "Whiplash"}), 200, "k: search")["total"]
    check(hits >= 1, f"k: the search finds {hits} Whiplash dossiers")
    found = expect(
        organizer.get("/api/templates", params={"q": "Whiplash", "format": "movienight"}),
        200,
        "k: search the templates",
    )
    source = next(card for card in found["items"] if card["state"] == "archived")
    start = (datetime.now(UTC) + timedelta(days=47)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    made = expect(
        organizer.post(f"/api/events/{source['id']}/clone", json={"startsAt": start.isoformat()}),
        201,
        "k: clone",
    )
    eid = made["event"]["id"]
    first = m4.poster(organizer, eid)
    m4.fire(organizer, eid, "T01")
    items = expect(organizer.get(f"/api/events/{eid}/checklist"), 200, "k: checklist")["items"]
    for item in (i for i in items if i["phase"] == "planning"):
        expect(
            organizer.post(f"/api/checklist-items/{item['id']}/done", json={"done": True}),
            200,
            f"k: done '{item['text']}'",
        )
    m4.fire(organizer, eid, "T02")
    question = expect(
        editor.post(
            f"/api/events/{eid}/comments",
            json={"bodyMd": "Motiv passt nicht zum Termin.", "anchor": {"field": "hero"}},
        ),
        201,
        "k: question on the poster",
    )
    m4.fire(editor, eid, "T03", note="Bitte Motiv tauschen")
    fresh = organizer.post(
        f"/api/attachments/{first}/replace",
        data=m4.RIGHTS,
        files={"file": ("neu.png", m4.png_bytes(1500, 1000, "#cc6633"), "image/png")},
    )
    replaced = expect(fresh, 201, "k: poster replaced")
    m4.scanned(organizer, replaced["id"], eid)
    m4.fire(organizer, eid, "T02")
    expect(editor.post(f"/api/comments/{question['id']}/resolve"), 200, "k: resolve the question")
    confirm_location(editor, eid)
    m4.fire(editor, eid, "T04")
    m4.fire(editor, eid, "T05")
    with anonymous() as client:
        feed = client.get("/api/public/feed/events", params={"limit": 500}).json()["items"]
        ics = client.get("/ics/all.ics").text
    item = next((i for i in feed if i["id"] == eid), None)
    check(
        item is not None and item["image"] is not None,
        "k: the clone is in the feed with its poster",
    )
    check(f"UID:{eid}@" in ics, "k: the clone is in the ICS")
    step(f"k: {made['event']['title']} live from template {source['title']}")
