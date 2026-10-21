"""M5b acceptance, rights and leftovers: who publishes, removed routes, cache invalidation.

The submitter cannot publish, an organizer of another organization gets 404, the editorial
team publishes a foreign dossier. The routes of the pipeline (`/api/tasks`, transitions,
guards, the board view, image exception and friends) are gone. Renaming a category shows
in the feed right away (M5 review 1); the name is restored at the end.
"""

from __future__ import annotations

import time

import httpx

from scripts import dossier_api as dossier
from scripts.acceptance_common import check, expect, feed_items, step

GONE = (
    ("GET", "/api/tasks"),
    ("POST", "/api/events/{eid}/transitions/T04"),
    ("GET", "/api/events/{eid}/guards/T04"),
    ("POST", "/api/events/{eid}/actions/image-exception"),
    ("POST", "/api/events/{eid}/actions/assign-organization"),
    ("POST", "/api/events/{eid}/actions/acknowledge-changes"),
    ("POST", "/api/events/{eid}/actions/confirm-flyer"),
    ("POST", "/api/events/{eid}/actions/cancel"),
)


def check_rights(
    organizer: httpx.Client, editor: httpx.Client, submitter: httpx.Client, makers: httpx.Client
) -> None:
    """Item b: publish rights per role and the 404 rule."""
    own = dossier.create(submitter, "M5b Einreichung")
    expect(
        submitter.post(f"/api/events/{own}/publish", json={}, headers=dossier.etag(submitter, own)),
        403,
        "b: the submitter cannot publish",
    )
    eid = dossier.create(organizer, "M5b Fremd")
    expect(makers.get(f"/api/events/{eid}"), 404, "b: organizer-makers reads the FSI dossier: 404")
    expect(
        makers.post(f"/api/events/{eid}/publish", json={}, headers={"If-Match": '"1"'}),
        404,
        "b: organizer-makers publishes the FSI dossier: 404",
    )
    done = dossier.act(editor, eid, "publish")
    check(done["state"] == "published", "b: the editor publishes a foreign dossier")
    done = dossier.act(editor, own, "publish")
    check(done["state"] == "published", "b: the editor publishes the submitter's draft")


def check_gone(organizer: httpx.Client) -> None:
    """Item f: the routes of the pipeline answer 404 (the board view 422)."""
    eid = dossier.create(organizer, "M5b Rückbau")
    for method, path in GONE:
        status = organizer.request(method, path.format(eid=eid), json={}).status_code
        check(status in {404, 405}, f"f: {method} {path} -> {status}")
    board = organizer.get("/api/events", params={"view": "board"}).status_code
    check(board in {404, 422}, f"f: GET /api/events?view=board -> {board}")


def _category_name_in_feed(slug: str, name: str, timeout: int = 30) -> bool:
    for _ in range(timeout):
        names = {c["name"] for i in feed_items() for c in i["categories"] if c["slug"] == slug}
        if names == {name}:
            return True
        time.sleep(1)
    return False


def check_invalidation(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Item h: a category rename invalidates the feed (M5 review 1)."""
    dossier.published(organizer, "M5b Kategorie", category="kino")
    rows = expect(editor.get("/api/admin/categories"), 200, "h: categories")
    kino = next(row for row in rows if row["slug"] == "kino")
    try:
        expect(
            editor.patch(f"/api/admin/categories/{kino['id']}", json={"name": "Kino M5b"}),
            200,
            "h: rename the category",
        )
        check(_category_name_in_feed("kino", "Kino M5b"), "h: the feed shows the new name")
    finally:
        editor.patch(f"/api/admin/categories/{kino['id']}", json={"name": kino["name"]})
    check(_category_name_in_feed("kino", kino["name"]), "h: the old name is back in the feed")
    step("ok   h: category rename invalidates the public cache")
