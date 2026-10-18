"""M1 acceptance run against a host-run API and the dev stack (`python -m scripts.m1_acceptance`).

The script logs in through the real OIDC flow of the dev Keycloak (login form, code,
callback with PKCE), so roles come from the IdP groups. It then walks the M1 criterion:
`organizer-fsi` creates a dossier, uploads a poster with alt text and credit and fires
T01 and T02; `editor` fires T04 and T05; the public feed lists the event and serves its
derivative. A second dossier without a poster gets 422 `image_required` on T04, and
direct SQL as `events_app` fails on the publish trigger for UPDATE and INSERT.

Only for the local stack: it refuses any API or IdP host other than localhost. The
callback URL of the dev env points at `ng serve` (:4200); the script replays it against
the API itself, which works because cookies are not port-bound.
"""

from __future__ import annotations

import asyncio
import html
import io
import os
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import get_sessionmaker
from app.modules.audit.service import AuditService
from app.settings import get_settings

API = os.environ.get("M1_API", "http://localhost:8000")
PASSWORD = "password"
_FORM_ACTION = re.compile(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"')


def step(message: str) -> None:
    """Print one protocol line."""
    print(f"[m1] {message}", flush=True)


def check(condition: bool, message: str) -> None:
    """Stop the run with `message` unless `condition` holds."""
    if not condition:
        print(f"[m1] FAIL: {message}", flush=True)
        sys.exit(1)
    step(f"ok   {message}")


def _to_api(url: str) -> str:
    """Point a URL of the dev frontend (any localhost port) at the API."""
    parts, api = urlsplit(url), urlsplit(API)
    return urlunsplit((api.scheme, api.netloc, parts.path, parts.query, ""))


def login(username: str) -> httpx.Client:
    """Log in `username` through Keycloak; return a client with session and CSRF header."""
    client = httpx.Client(base_url=API, timeout=20.0)
    to_idp = client.get("/api/auth/login", follow_redirects=False)
    check(to_idp.status_code in {302, 303, 307}, f"{username}: /api/auth/login redirects")
    idp_url = to_idp.headers["location"]
    check(urlsplit(idp_url).hostname == "localhost", "IdP is the local Keycloak")
    form = client.get(idp_url, follow_redirects=True)
    # Keycloak marks its cookies Secure even on http; browsers send them to localhost anyway.
    for cookie in client.cookies.jar:
        cookie.secure = False
    action = _FORM_ACTION.search(form.text)
    check(action is not None, f"{username}: Keycloak shows the login form")
    assert action is not None
    back = client.post(
        html.unescape(action.group(1)),
        data={"username": username, "password": PASSWORD, "credentialId": ""},
        follow_redirects=False,
    )
    callback = back.headers.get("location", "")
    check("/api/auth/callback" in callback, f"{username}: Keycloak returns a code")
    done = client.get(_to_api(callback), follow_redirects=False)
    check(done.status_code in {302, 303, 307}, f"{username}: callback opens the session")
    client.get("/api/auth/me")
    token = client.cookies.get("XSRF-TOKEN")
    if token:
        client.headers["X-XSRF-TOKEN"] = token
    return client


def expect(response: httpx.Response, status: int, what: str) -> Any:
    """Check the status of `response`; return its JSON body."""
    body = response.json() if response.content else {}
    detail = "" if response.status_code == status else f" (got {response.status_code}: {body})"
    check(response.status_code == status, f"{what} -> {status}{detail}")
    return body


def poster_png() -> bytes:
    """Draw a 1200x800 PNG test poster."""
    image = Image.new("RGB", (1200, 800), (24, 96, 160))
    for x in range(0, 1200, 40):
        image.paste((240, 200, 40), (x, 380, x + 20, 420))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def create_dossier(client: httpx.Client, title: str) -> dict[str, Any]:
    """Create a complete dossier in the organization `fsi` (T00)."""
    orgs = expect(client.get("/api/organizations", params={"creatable": "true"}), 200, "orgs")
    org_items = orgs if isinstance(orgs, list) else orgs["items"]
    fsi = next(o for o in org_items if o["slug"] == "fsi")
    cats = expect(client.get("/api/categories"), 200, "categories")
    category = (cats if isinstance(cats, list) else cats["items"])[0]
    start = (datetime.now(UTC) + timedelta(days=14)).replace(microsecond=0)
    body = {
        "title": title,
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=3)).isoformat(),
        "organizationId": fsi["id"],
        "venueText": "Kinosaal 9-133",
        "primaryCategoryId": category["id"],
        "summary": "Abnahmelauf M1",
    }
    event = expect(client.post("/api/events", json=body), 201, f"create '{title}' (T00)")
    check(event["state"] == "idea", "new dossier is in idea")
    return event


def fire(client: httpx.Client, event_id: str, transition: str, status: int = 200) -> Any:
    """Fire `transition` on the event; return the response body."""
    response = client.post(f"/api/events/{event_id}/transitions/{transition}", json={})
    return expect(response, status, f"{transition} on {event_id[:8]}")


def wait_for_derivatives(client: httpx.Client, event_id: str) -> dict[str, Any]:
    """Poll the event until the worker has scanned and derived its poster."""
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        poster = client.get(f"/api/events/{event_id}").json()["poster"]
        if poster["scanStatus"] == "clean" and poster["derivatives"]:
            return poster
        if poster["scanStatus"] in {"infected", "error"}:
            break
        time.sleep(2)
    check(False, "worker scanned (ClamAV) and derived the poster within 120 s")
    raise AssertionError


def happy_path(organizer: httpx.Client, editor: httpx.Client) -> str:
    """Walk one dossier from idea to live and through the public feed; return its id."""
    event = create_dossier(organizer, f"M1 Movienight {int(time.time())}")
    eid = event["id"]
    upload = organizer.post(
        f"/api/events/{eid}/poster",
        files={"file": ("poster.png", poster_png(), "image/png")},
        data={
            "altText": "Blaues Plakat mit gelbem Band",
            "credit": "STUPA",
            "rightsBasis": "own_work",
        },
    )
    attachment = expect(upload, 201, "poster upload with alt text and credit")
    check(attachment["scanStatus"] == "pending", "poster starts pending")
    poster = wait_for_derivatives(organizer, eid)
    step(f"     derivatives {sorted(poster['derivatives'])}")
    fire(organizer, eid, "T01")
    fire(organizer, eid, "T02")
    fire(organizer, eid, "T04", 403)
    approved = fire(editor, eid, "T04")
    check(bool(approved["slug"]) and approved["approvedBy"], f"T04 set slug {approved['slug']}")
    live = fire(editor, eid, "T05")
    check(live["state"] == "live", "event is live")
    feed = httpx.get(f"{API}/api/public/feed/events", timeout=20.0)
    check("set-cookie" not in feed.headers, "feed sets no cookie")
    item = next((i for i in expect(feed, 200, "public feed")["items"] if i["id"] == eid), None)
    check(item is not None, "event appears in the feed")
    assert item is not None
    check(item["image"] is not None and item["image"]["alt"], f"feed image {item['image']['url']}")
    media = httpx.get(_to_api(item["image"]["url"]), timeout=20.0)
    check(
        media.status_code == 200 and media.headers["content-type"] == "image/webp",
        f"derivative served as webp ({len(media.content)} bytes)",
    )
    return eid


def no_poster_path(organizer: httpx.Client, editor: httpx.Client) -> str:
    """A dossier without a poster cannot be approved; return its id."""
    eid = create_dossier(organizer, f"M1 ohne Plakat {int(time.time())}")["id"]
    fire(organizer, eid, "T01")
    fire(organizer, eid, "T02")
    problem = fire(editor, eid, "T04", 422)
    check(problem["code"] == "image_required", "T04 without poster: code image_required")
    codes = [r["code"] for r in problem["reasons"]]
    check("image_required" in codes, f"reasons[] {codes}")
    guards = expect(editor.get(f"/api/events/{eid}/guards/T04"), 200, "guard list T04")
    check(not guards["allowed"], "guards: T04 not allowed")
    return eid


async def sql_trigger(event_id: str) -> None:
    """Direct SQL as the runtime role must fail on `enforce_publish_image`."""
    engine = create_async_engine(get_settings().database_url)
    statements = {
        "UPDATE state=live": "UPDATE event SET state = 'live' WHERE id = :id",
        "UPDATE state=approved": "UPDATE event SET state = 'approved' WHERE id = :id",
        "INSERT state=live": (
            "INSERT INTO event (title, starts_at, ends_at, organization_id, state, created_by) "
            "SELECT 'sql bypass', starts_at, ends_at, organization_id, 'live', 'sql' "
            "FROM event WHERE id = :id"
        ),
    }
    try:
        for label, statement in statements.items():
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(statement), {"id": event_id})
            except DBAPIError as exc:
                sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
                check(sqlstate == "23514", f"SQL {label} fails with 23514 ({str(exc.orig)[:90]})")
            else:
                check(False, f"SQL {label} must fail")
    finally:
        await engine.dispose()


async def audit_chain() -> None:
    """Verify the audit hash chain of the dev database."""
    async with get_sessionmaker()() as session:
        result = await AuditService(session).verify_chain()
    check(result.valid, f"audit chain valid ({result.checked} entries)")


def main() -> None:
    """Run the whole acceptance walk."""
    check(urlsplit(API).hostname in {"localhost", "127.0.0.1"}, f"API {API} is local")
    organizer, editor = login("organizer-fsi"), login("editor")
    me = expect(organizer.get("/api/auth/me"), 200, "/api/auth/me organizer-fsi")
    check(
        me["organizations"] == [{"slug": "fsi", "role": "organizer"}], f"orgs {me['organizations']}"
    )
    me_editor = expect(editor.get("/api/auth/me"), 200, "/api/auth/me editor")
    check("editor" in me_editor["roles"], f"editor roles {me_editor['roles']}")
    happy_path(organizer, editor)
    blocked = no_poster_path(organizer, editor)
    asyncio.run(sql_trigger(blocked))
    asyncio.run(audit_chain())
    step("M1 acceptance: all checks passed")


if __name__ == "__main__":
    main()
