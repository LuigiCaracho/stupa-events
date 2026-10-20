"""M4 acceptance run against a host-run API and the dev stack (`python -m scripts.m4_acceptance`).

Criterion (PLAN 16.1, row M4; contract 9.3 a to m): EICAR lands in quarantine, SVG and
`.docm` answer 415, a bomb image is refused, `€` and emoji in file names never cause a 500;
an open question on the poster blocks T04 until it is resolved; a checklist from the
category template recomputes its due dates after a date change; a mail template renders
its placeholders and refuses an unknown one; quotes stay invisible to other organizations;
mails leave only while Redis runs. Item h (roundtrip corpus) and n (mobile, axe) belong to
Jest and Playwright. Each person logs in through the real OIDC flow; SQL only reads, or
moves the clocks of the media garbage collector.

Only for the local stack. It needs the migrated and seeded database, a running worker with
ClamAV, and permission to stop and start the dev Redis container.
"""

from __future__ import annotations

import io
import time
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from PIL import Image

from app.modules.notifications.mail import compute_idempotency_key
from scripts import acceptance_common as common
from scripts import m4_ops as ops
from scripts.acceptance_common import API, check, expect, login, step
from tests._support.factories import png_bytes
from tests._support.samples import EICAR, bomb_png, jpeg_with_gps, ooxml_bytes, pdf_bytes, svg_bytes

common.PREFIX[0] = "m4"
RIGHTS = {"altText": "Ein Plakat", "credit": "Foto: Ada", "rightsBasis": "own_work"}
BERLIN = ZoneInfo("Europe/Berlin")


def stamp() -> str:
    """Return a title suffix that keeps repeated runs apart."""
    return datetime.now(UTC).strftime("%H%M%S")


def ref_id(client: httpx.Client, path: str, slug: str, **params: str) -> str:
    """Return the id of an organization or category by slug."""
    rows = expect(client.get(path, params=params), 200, path)
    return next(row["id"] for row in rows if row["slug"] == slug)


def create(client: httpx.Client, title: str, *, category: str = "kino", days: int = 40) -> str:
    """Create a dossier of the FSI in `planning` and return its id."""
    start = (datetime.now(UTC) + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)
    body = {
        "title": f"{title} {stamp()}",
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=3)).isoformat(),
        "organizationId": ref_id(client, "/api/organizations", "fsi", creatable="true"),
        "venueText": "Kinosaal 9-133",
        "primaryCategoryId": ref_id(client, "/api/categories", category),
        "summary": "Ein Abend mit Programm.",
    }
    eid = expect(client.post("/api/events", json=body), 201, f"create '{body['title']}'")["id"]
    fire(client, eid, "T01")
    return eid


def etag(client: httpx.Client, eid: str) -> dict[str, str]:
    """The current version of the dossier as `If-Match`."""
    return {"If-Match": client.get(f"/api/events/{eid}").headers.get("etag", "")}


def fire(client: httpx.Client, eid: str, tid: str, status: int = 200, **body: object) -> dict:
    """Fire a transition and check the status."""
    response = client.post(
        f"/api/events/{eid}/transitions/{tid}", json=body, headers=etag(client, eid)
    )
    return expect(response, status, f"{tid} -> {status}")


def upload(
    client: httpx.Client, eid: str, name: str, data: bytes, kind: str = "other", **form: str
) -> httpx.Response:
    """Upload one attachment."""
    return client.post(
        f"/api/events/{eid}/attachments",
        data={"kind": kind, **form},
        files={"file": (name, data, "application/octet-stream")},
    )


def scanned(client: httpx.Client, attachment_id: str, eid: str) -> dict:
    """Wait until the worker finished the scan (and the poster derivatives) of an attachment."""
    for _ in range(90):
        rows = client.get(
            f"/api/events/{eid}/attachments", params={"includeRetired": "true"}
        ).json()
        row = next(r for r in rows if r["id"] == attachment_id)
        finished = row["scanStatus"] in {"clean", "infected", "error"}
        if finished and (
            row["kind"] != "poster" or row["scanStatus"] != "clean" or _derived(client, eid)
        ):
            return row
        time.sleep(1)
    check(False, f"attachment {attachment_id} is scanned within 90 s")
    raise AssertionError


def _derived(client: httpx.Client, eid: str) -> bool:
    poster = client.get(f"/api/events/{eid}").json()["poster"]
    return bool(poster and poster["derivatives"])


def raw(response: httpx.Response, status: int, what: str) -> bytes:
    """Check the status of a streamed (non-JSON) response; return its bytes."""
    check(response.status_code == status, f"{what} -> {status} (got {response.status_code})")
    return response.content


def reasons(response: httpx.Response) -> list[str]:
    """Return the reason codes of a Problem+JSON body."""
    return [r["code"] for r in response.json().get("reasons", [])]


def check_quarantine_and_types(organizer: httpx.Client) -> None:
    """Items a to d and m: scan, refused types, bomb image, names, EXIF."""
    eid = create(organizer, "M4 Anhänge")
    infected = expect(upload(organizer, eid, "eicar.txt", EICAR), 201, "a: EICAR upload")
    early = organizer.get(f"/api/attachments/{infected['id']}/download")
    check(early.status_code in {409, 410}, f"a: download before the scan is {early.status_code}")
    row = scanned(organizer, infected["id"], eid)
    check(row["scanStatus"] == "infected", "a: the worker marks EICAR as infected")
    gone = organizer.get(f"/api/attachments/{infected['id']}/download")
    check(gone.status_code == 410 and gone.json()["code"] == "attachment_infected", "a: 410")
    key = ops.query("SELECT storage_key FROM attachment WHERE id = :i", i=infected["id"])[0][0]
    check(key is None, "a: the object of the infected file is gone (storage_key NULL)")
    clean = expect(upload(organizer, eid, "notiz.txt", b"Hallo Welt\n"), 201, "a: clean upload")
    check(scanned(organizer, clean["id"], eid)["scanStatus"] == "clean", "a: second file clean")
    raw(organizer.get(f"/api/attachments/{clean['id']}/download"), 200, "a: clean download")

    for name, data, kind in (
        ("bild.svg", svg_bytes(), "other"),
        ("bild.svg", svg_bytes(), "poster"),
        ("brief.docm", ooxml_bytes(macro=True), "other"),
        ("brief.docx", ooxml_bytes(macro=True), "other"),
    ):
        refused = upload(organizer, eid, name, data, kind)
        expect(refused, 415, f"b: {name} as {kind}")
        check(
            refused.json()["code"] == "unsupported_media_type", f"b: {name} unsupported_media_type"
        )

    before = {u: ops.unit_memory_kib(u) for u in ("stupa-api", "stupa-worker")}
    bomb = bomb_png()
    refused = upload(organizer, eid, "bombe.png", bomb, "poster", **RIGHTS)
    expect(refused, 422, f"c: bomb PNG 30000x30000 ({len(bomb) // 1024} KiB)")
    check(refused.json()["code"] == "image_rejected", "c: code image_rejected")
    after = {u: ops.unit_memory_kib(u) for u in ("stupa-api", "stupa-worker")}
    for unit in before:
        grown = (after[unit]["VmHWM"] - before[unit]["VmHWM"]) // 1024
        step(f"c: {unit} RSS {after[unit]['VmRSS'] // 1024} MiB, peak +{grown} MiB")
        check(grown < 200, f"c: {unit} peak memory grows less than 200 MiB")

    for name, data in (
        ("Rechnung €.pdf", pdf_bytes()),
        ("Plakat 5 € 🎬.pdf", pdf_bytes()),
        ("🎉.png", png_bytes(400, 300)),
    ):
        made = expect(upload(organizer, eid, name, data), 201, f"d: upload '{name}'")
        check(made["displayName"] == name, f"d: display name kept '{name}'")
        scanned(organizer, made["id"], eid)
        got = organizer.get(f"/api/attachments/{made['id']}/download")
        disposition = got.headers.get("content-disposition", "")
        check(got.status_code == 200 and "filename*=UTF-8''" in disposition, f"d: {disposition}")

    gps = expect(upload(organizer, eid, "gps.jpg", jpeg_with_gps()), 201, "m: JPEG with GPS")
    scanned(organizer, gps["id"], eid)
    stored = organizer.get(f"/api/attachments/{gps['id']}/download").content
    check(b"Exif" not in stored and not Image.open(io.BytesIO(stored)).getexif(), "m: no EXIF")
    preview = organizer.get(f"/api/attachments/{gps['id']}/preview")
    for _ in range(30):
        if preview.status_code != 404:
            break
        time.sleep(1)
        preview = organizer.get(f"/api/attachments/{gps['id']}/preview")
    check(
        preview.status_code == 200 and b"EXIF" not in preview.content.upper(),
        "m: preview without EXIF",
    )
    with open("/tmp/m4-gps-download.jpg", "wb") as out:
        out.write(stored)
    step("m: download saved to /tmp/m4-gps-download.jpg for the exiftool cross-check")


def poster(client: httpx.Client, eid: str, width: int = 1400) -> str:
    """Upload a usable poster and wait for scan and derivatives."""
    data = png_bytes(width, 900)
    made = expect(upload(client, eid, "plakat.png", data, "poster", **RIGHTS), 201, "poster")
    check(scanned(client, made["id"], eid)["scanStatus"] == "clean", "poster scanned clean")
    return made["id"]


def check_hero_question(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item e: a question on the poster blocks T04 until it is resolved, even after replacement."""
    eid = create(organizer, "M4 Rückfrage")
    first = poster(organizer, eid)
    fire(organizer, eid, "T02")
    question = expect(
        editor.post(
            f"/api/events/{eid}/comments",
            json={"bodyMd": "Ist das Motiv freigegeben?", "anchor": {"field": "hero"}},
        ),
        201,
        "e: question on the poster",
    )
    report = expect(editor.get(f"/api/events/{eid}/guards/T04"), 200, "e: guard report")
    check("open_comment_on_hero" in [r["code"] for r in report["reasons"]], "e: guard names it")
    blocked = editor.post(f"/api/events/{eid}/transitions/T04", json={}, headers=etag(editor, eid))
    expect(blocked, 422, "e: T04 blocked")
    check(blocked.json()["code"] == "open_comment_on_hero", "e: code open_comment_on_hero")
    data = png_bytes(1500, 1000, "#cc6633")
    fresh = editor.post(
        f"/api/attachments/{first}/replace",
        data=RIGHTS,
        files={"file": ("neu.png", data, "image/png")},
    )
    replaced = expect(fresh, 201, "e: poster replaced")
    check(scanned(editor, replaced["id"], eid)["scanStatus"] == "clean", "e: replacement clean")
    again = editor.post(f"/api/events/{eid}/transitions/T04", json={}, headers=etag(editor, eid))
    check(
        again.status_code == 422 and again.json()["code"] == "open_comment_on_hero",
        "e: replacing the poster does not resolve the question",
    )
    expect(editor.post(f"/api/comments/{question['id']}/resolve"), 200, "e: resolve")
    fire(editor, eid, "T04")


def check_checklist(organizer: httpx.Client) -> None:
    """Item f: template of `party`, start moved by ten days, recomputed due dates, T02 blocked."""
    eid = create(organizer, "M4 Party", category="party")
    applied = expect(
        organizer.post(f"/api/events/{eid}/checklist/apply-template", json={}), 200, "f: template"
    )
    step(f"f: template {applied['template']} added {applied['added']} items")
    check(applied["template"]["slug"] == "party" and applied["added"] > 0, "f: party template")
    items = {i["text"]: i for i in applied["items"]}
    manual_at = datetime(2031, 5, 5, 8, 0, tzinfo=UTC)
    manual = items["Technik bestätigen"]
    expect(
        organizer.patch(
            f"/api/checklist-items/{manual['id']}", json={"dueAt": manual_at.isoformat()}
        ),
        200,
        "f: manual due date",
    )
    done = expect(
        organizer.post(
            f"/api/checklist-items/{items['Plakat bestellen']['id']}/done", json={"done": True}
        ),
        200,
        "f: one item done",
    )
    event = organizer.get(f"/api/events/{eid}").json()
    start = datetime.fromisoformat(event["startsAt"]) + timedelta(days=10)
    end = datetime.fromisoformat(event["endsAt"]) + timedelta(days=10)
    moved = expect(
        organizer.patch(
            f"/api/events/{eid}",
            json={"rev": event["rev"], "startsAt": start.isoformat(), "endsAt": end.isoformat()},
        ),
        200,
        "f: startsAt +10 days",
    )
    after = {i["text"]: i for i in organizer.get(f"/api/events/{eid}/checklist").json()["items"]}
    shifted = [
        t
        for t, i in items.items()
        if i["fromTemplate"] and t not in {manual["text"], "Plakat bestellen"}
    ]
    check(moved["checklistRecomputed"] == len(shifted), f"f: checklistRecomputed = {len(shifted)}")
    for text in shifted:
        delta = datetime.fromisoformat(after[text]["dueAt"]) - datetime.fromisoformat(
            items[text]["dueAt"]
        )
        check(abs(delta - timedelta(days=10)) <= timedelta(hours=1), f"f: '{text}' +10 days")
    check(
        datetime.fromisoformat(after[manual["text"]]["dueAt"]) == manual_at, "f: manual unchanged"
    )
    check(after["Plakat bestellen"]["dueAt"] == done["dueAt"], "f: done item unchanged")
    poster(organizer, eid)
    blocked = organizer.post(
        f"/api/events/{eid}/transitions/T02", json={}, headers=etag(organizer, eid)
    )
    expect(blocked, 422, "f: T02 with open required planning items")
    check(
        "checklist_open" in reasons(blocked) or blocked.json()["code"] == "checklist_open",
        "f: reason checklist_open",
    )


def check_mail_template(organizer: httpx.Client) -> None:
    """Item g: the four placeholders render in local time; an unknown one is refused."""
    eid = create(organizer, "M4 Mail")
    body = (
        "Hallo,\n{{ event.title }} am {{ event.starts_local }} im {{ venue.name }}.\n"
        "{{ org.name }}\n"
    )
    saved = organizer.put(
        f"/api/events/{eid}/mail-templates/new",
        json={"title": "Einladung", "subject": "Einladung: {{ event.title }}", "bodyMd": body},
    )
    tpl = expect(saved, 201, "g: template saved")
    rendered = expect(
        organizer.post(f"/api/events/{eid}/mail-templates/{tpl['id']}/render-preview", json={}),
        200,
        "g: render",
    )
    event = organizer.get(f"/api/events/{eid}").json()
    local = (
        datetime.fromisoformat(event["startsAt"]).astimezone(BERLIN).strftime("%d.%m.%Y, %H:%M Uhr")
    )
    step(f"g: {rendered['subject']!r} / {rendered['body']!r}")
    check(rendered["subject"] == f"Einladung: {event['title']}", "g: subject")
    check(
        local in rendered["body"] and "Kinosaal 9-133" in rendered["body"], f"g: local time {local}"
    )
    bad = organizer.post(
        f"/api/events/{eid}/mail-templates/{tpl['id']}/render-preview",
        json={"bodyMd": "Raum {{ event.raum }}"},
    )
    expect(bad, 422, "g: unknown placeholder")
    problem = bad.json()
    unknown = [r for r in problem["reasons"] if r["code"] == "unknown_placeholder"]
    check(
        problem["code"] == "template_invalid" and bool(unknown),
        "g: template_invalid/unknown_placeholder",
    )
    step(f"g: reason {unknown[0]}")
    check(bool(unknown[0].get("allowed")), "g: the reason lists the allowed paths")


def check_quotes(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item i: quotes are invisible to other organizations, 403 inside without the right."""
    eid = create(organizer, "M4 Angebote")
    file = expect(
        upload(organizer, eid, "angebot.pdf", pdf_bytes(), "quote", visibility="team"),
        201,
        "i: file",
    )
    scanned(organizer, file["id"], eid)
    quote = expect(
        organizer.post(
            f"/api/events/{eid}/quotes",
            json={
                "grp": "Technik",
                "vendor": "PA-Verleih",
                "amountCents": 123457,
                "attachmentId": file["id"],
            },
        ),
        201,
        "i: quote created",
    )
    for user in ("organizer-makers", "member"):
        other = login(user)
        expect(other.get(f"/api/events/{eid}/quotes"), 404, f"i: {user} list")
        # M2 gate rule: a missing route right is 403 before any id; `member` lacks `dossier.attach`.
        gate = 404 if user == "organizer-makers" else 403
        expect(other.post(f"/api/quotes/{quote['id']}/select"), gate, f"i: {user} select")
        expect(other.get(f"/api/attachments/{file['id']}/download"), 404, f"i: {user} file")
    viewer = login("viewer-fsi")
    denied = viewer.get(f"/api/events/{eid}/quotes")
    expect(denied, 403, "i: viewer-fsi same org")
    check("123457" not in denied.text, "i: the 403 body carries no amount")
    seen = expect(editor.get(f"/api/events/{eid}/quotes"), 200, "i: editor")
    amounts = [q["amountCents"] for g in seen["groups"] for q in g["quotes"]]
    check(123457 in amounts, "i: editor sees the amount")
    expect(organizer.post(f"/api/quotes/{quote['id']}/select"), 200, "i: organizer selects")
    for path in (f"/api/events/{eid}", f"/api/events/{eid}/revisions", "/api/events"):
        check("123457" not in organizer.get(path).text, f"i: no amount in {path}")
    check("123457" not in httpx.get(f"{API}/api/public/feed/events").text, "i: no amount in feed")
    check(not ops.query("SELECT 1 FROM audit_entry WHERE data::text LIKE '%123457%'"), "i: audit")


def mail_job(eid: str, sub: str, kind: str) -> str:
    """Return the mail job id of the notification `kind` for `sub` on dossier `eid`."""
    rows = ops.query(
        "SELECT id FROM notification WHERE event_id = :e AND recipient_sub = :s AND kind = :k",
        e=eid,
        s=sub,
        k=kind,
    )
    check(len(rows) == 1, f"one {kind} row for the recipient")
    return compute_idempotency_key("notif", str(rows[0][0]))


def check_mail_needs_redis(organizer: httpx.Client, editor_sub: str) -> None:
    """Item j: with Redis T02 mails the editors; without it T02 works and the mail is dropped."""
    with_redis = create(organizer, "M4 Mail an")
    poster(organizer, with_redis)
    fire(organizer, with_redis, "T02")
    job = mail_job(with_redis, editor_sub, "review_requested")
    check(ops.job_result(job) == "sent", f"j: mail job {job[:20]}… sent by the worker")
    without = create(organizer, "M4 Mail aus")
    poster(organizer, without)
    since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ops.redis_down()
    try:
        fire(organizer, without, "T02")
        rows = ops.query(
            "SELECT count(*) FROM notification WHERE event_id = :e AND kind = 'review_requested'",
            e=without,
        )
        check(rows[0][0] >= 1, "j: in-app rows exist without Redis")
    finally:
        ops.redis_up()
    log = [line for line in ops.unit_log("stupa-api", since).splitlines() if "mail dropped" in line]
    step(f"j: log {log[:1]}")
    check(bool(log) and not any("@" in line for line in log), "j: warning logged, no address")
    try:
        ops.job_result(mail_job(without, editor_sub, "review_requested"), timeout=5)
        check(False, "j: the dropped mail has no job")
    except Exception as exc:  # noqa: BLE001 - arq raises on an unknown job
        step(f"ok   j: no mail job for the dropped mail ({type(exc).__name__})")


def check_due_reminder(organizer: httpx.Client, organizer_sub: str) -> None:
    """Item k: an item due tomorrow gets exactly one reminder mail, a second run none."""
    eid = create(organizer, "M4 Fällig")
    tomorrow = datetime.now(BERLIN).date() + timedelta(days=1)
    due = datetime.combine(tomorrow, datetime.min.time(), BERLIN).replace(hour=12)
    item = expect(
        organizer.post(
            f"/api/events/{eid}/checklist/items",
            json={
                "text": "Getränke bestellen",
                "phase": "planning",
                "assigneeSub": organizer_sub,
                "dueAt": due.isoformat(),
            },
        ),
        201,
        "k: item due tomorrow",
    )
    first = ops.run_job("send_due_reminders")
    second = ops.run_job("send_due_reminders")
    step(f"k: {first} / {second}")
    check("mails=0" in second, "k: the second run sends nothing")
    rows = ops.query(
        "SELECT id FROM notification WHERE kind = 'checklist_due' AND dedupe_key LIKE :k",
        k=f"checklist_due:{item['id']}:%",
    )
    check(len(rows) == 1, "k: exactly one checklist_due row")
    job = compute_idempotency_key("notif", str(rows[0][0]))
    check(ops.job_result(job) == "sent", "k: exactly one reminder mail sent")


def check_media_gc(organizer: httpx.Client) -> None:
    """Item l: an old unreferenced image goes in two runs, one from an old revision stays."""
    eid = create(organizer, "M4 GC")
    ids = []
    for color in ("#112233", "#445566"):
        image = organizer.post(
            "/api/media/images", files={"file": ("b.png", png_bytes(300, 200, color), "image/png")}
        )
        ids.append(expect(image, 201, "l: markdown image")["id"])
    kept, orphan = ids
    doc = organizer.post(
        f"/api/events/{eid}/documents",
        json={"kind": "howto", "title": "Anleitung", "bodyMd": f"![x](/api/media/images/{kept})\n"},
    )
    made = expect(doc, 201, "l: document with the image")
    expect(
        organizer.put(
            f"/api/documents/{made['id']}",
            json={"bodyMd": "Ohne Bild\n"},
            headers={"If-Match": '"1"'},
        ),
        200,
        "l: revision 2 drops the image",
    )
    old = datetime.now(UTC) - timedelta(days=8)
    ops.query(
        "UPDATE markdown_image SET created_at = :t WHERE id IN (:a, :b)", t=old, a=kept, b=orphan
    )
    day = datetime.now(UTC).strftime("%Y%m%d")
    for run in (1, 2):
        ops.redis_delete(f"gc_media:{day}")
        step(f"l: run {run}: {ops.run_job('gc_media')}")
        ops.query(
            "UPDATE markdown_image SET gc_marked_at = :t WHERE gc_marked_at IS NOT NULL", t=old
        )
    left = {
        str(r[0])
        for r in ops.query("SELECT id FROM markdown_image WHERE id IN (:a, :b)", a=kept, b=orphan)
    }
    check(orphan not in left, "l: the orphan is deleted")
    check(kept in left, "l: the image of the old revision stays")
    raw(organizer.get(f"/api/media/images/{kept}"), 200, "l: kept image still streams")
    raw(organizer.get(f"/api/media/images/{orphan}"), 404, "l: deleted image is gone")


def main() -> None:
    """Run the M4 acceptance checks in contract order."""
    ops.reset_upload_limits()
    organizer, editor = login("organizer-fsi"), login("editor")
    editor_sub = editor.get("/api/auth/me").json()["sub"]
    organizer_sub = organizer.get("/api/auth/me").json()["sub"]
    check_quarantine_and_types(organizer)
    check_hero_question(organizer, editor)
    check_checklist(organizer)
    check_mail_template(organizer)
    check_quotes(organizer, editor)
    check_mail_needs_redis(organizer, editor_sub)
    check_due_reminder(organizer, organizer_sub)
    check_media_gc(organizer)
    step(f"all checks passed ({date.today().isoformat()})")


if __name__ == "__main__":
    main()
