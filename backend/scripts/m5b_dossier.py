"""M5b acceptance, documentation path: howto, poster, publish, clone from template, format.

The organization writes the howto, drops a poster and publishes the dossier itself; the feed
then carries the image. A second dossier goes out without a poster: it is published, the
hint `no_poster` warns and the feed says `image: null`. "Neu aus Vorlage" clones an archived
edition into a draft that carries the howto; "Als Format speichern" and the library still
answer on the new states.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx

from scripts import dossier_api as dossier
from scripts.acceptance_common import check, confirm_location, expect, feed_items
from tests._support.factories import png_bytes

RIGHTS = {"altText": "Ein Plakat", "credit": "Foto: Ada", "rightsBasis": "own_work"}
HOWTO = "## Ablauf\n\nSaal buchen, Technik prüfen, Einlass um 18:30."


def feed_item(eid: str, timeout: int = 60) -> dict | None:
    """Return the feed item of a dossier, waiting for the snapshot rebuild."""
    for _ in range(timeout):
        item = next((i for i in feed_items() if i["id"] == eid), None)
        if item is not None:
            return item
        time.sleep(1)
    return None


def write_howto(client: httpx.Client, eid: str) -> None:
    """Write the howto of a dossier."""
    expect(
        client.post(
            f"/api/events/{eid}/documents",
            json={"kind": "howto", "title": "Anleitung", "bodyMd": HOWTO},
        ),
        201,
        "a: the howto is written",
    )


def upload_poster(client: httpx.Client, eid: str) -> str:
    """Upload a poster and wait until scan and derivatives are done; return its id."""
    made = expect(
        client.post(
            f"/api/events/{eid}/poster",
            data=RIGHTS,
            files={"file": ("plakat.png", png_bytes(1400, 900), "image/png")},
        ),
        201,
        "a: poster upload",
    )
    for _ in range(90):
        poster = client.get(f"/api/events/{eid}").json().get("poster")
        if poster and poster.get("derivatives"):
            return made["id"]
        time.sleep(1)
    check(False, "a: the poster is scanned and derived within 90 s")
    raise AssertionError


def check_doc_path(organizer: httpx.Client) -> None:
    """Item a: dossier with howto and poster published by the organization itself."""
    eid = dossier.create(organizer, "M5b Doku mit Bild")
    write_howto(organizer, eid)
    upload_poster(organizer, eid)
    confirm_location(organizer, eid)
    done = dossier.act(organizer, eid, "publish")
    check(done["state"] == "published", "a: organizer-fsi publishes the own dossier")
    item = feed_item(eid)
    check(item is not None and item["image"] is not None, "a: in the feed with an image")
    codes = {h["code"] for h in organizer.get(f"/api/events/{eid}/hints").json()["items"]}
    check("no_poster" not in codes, f"a: with a poster no no_poster ({sorted(codes)})")

    bare = dossier.create(organizer, "M5b Doku ohne Bild")
    write_howto(organizer, bare)
    response = organizer.post(
        f"/api/events/{bare}/publish", json={}, headers=dossier.etag(organizer, bare)
    )
    out = expect(response, 200, "a: publish without a poster -> 200")
    check(out["poster"] is None and out["hintCount"] >= 1, f"a: hintCount {out['hintCount']}")
    hints = expect(organizer.get(f"/api/events/{bare}/hints"), 200, "a: hints")["items"]
    warn = {h["code"]: h["severity"] for h in hints}
    check(warn.get("no_poster") == "warn", f"a: no_poster warns on a published dossier ({warn})")
    item = feed_item(bare)
    check(item is not None and item["image"] is None, "a: feed image null without a poster")


def check_template(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item g: clone an archived edition into a draft with the howto; format and library."""
    source = dossier.create(organizer, "M5b Vorlage")
    write_howto(organizer, source)
    confirm_location(organizer, source)
    dossier.act(organizer, source, "publish")
    dossier.act(organizer, source, "archive")
    expect(organizer.get(f"/api/events/{source}/clone-preview"), 200, "g: clone preview")
    start = (datetime.now(UTC) + timedelta(days=60)).replace(minute=0, second=0, microsecond=0)
    made = expect(
        organizer.post(f"/api/events/{source}/clone", json={"startsAt": start.isoformat()}),
        201,
        "g: Neu aus Vorlage",
    )["event"]
    check(made["state"] == "draft", f"g: the clone is a draft ({made['state']})")
    docs = expect(organizer.get(f"/api/events/{made['id']}/documents"), 200, "g: documents")
    howto = next((d for d in docs if d["kind"] == "howto"), None)
    check(howto is not None, "g: the clone has a howto")
    assert howto is not None
    body = expect(organizer.get(f"/api/documents/{howto['id']}"), 200, "g: howto")["bodyMd"]
    check("Einlass" in body, "g: the clone carries the text of the howto")
    slug = f"m5b-{dossier.stamp()}"
    expect(
        organizer.post(
            f"/api/events/{source}/save-as-format", json={"slug": slug, "title": f"M5b {slug}"}
        ),
        201,
        "g: the organizer saves the archive as a format",
    )
    expect(organizer.get(f"/api/formats/{slug}"), 200, "g: the format reads back")
    expect(editor.get("/api/library"), 200, "g: the library answers")
