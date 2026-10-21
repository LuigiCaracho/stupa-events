"""Dossier helpers of the acceptance scripts: create, publish, archive and cancel over HTTP.

Every function takes a logged-in client (`acceptance_common.login`) and goes through the
real API, so the scripts exercise the same rules as the frontend. A dossier belongs to the
FSI; the title carries a time stamp that keeps repeated runs apart.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from scripts.acceptance_common import confirm_location, expect


def stamp() -> str:
    """Return a title suffix that keeps repeated runs apart."""
    return datetime.now(UTC).strftime("%H%M%S")


def ref_id(client: httpx.Client, path: str, slug: str, **params: str) -> str:
    """Return the id of an organization or category by slug."""
    rows = expect(client.get(path, params=params), 200, path)
    return next(row["id"] for row in rows if row["slug"] == slug)


def create(client: httpx.Client, title: str, *, category: str = "kino", days: int = 40) -> str:
    """Create a draft of the FSI and return its id."""
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
    return expect(client.post("/api/events", json=body), 201, f"create '{body['title']}'")["id"]


def etag(client: httpx.Client, eid: str) -> dict[str, str]:
    """The current version of the dossier as `If-Match`."""
    return {"If-Match": client.get(f"/api/events/{eid}").headers.get("etag", "")}


def act(client: httpx.Client, eid: str, action: str, status: int = 200, **body: object) -> dict:
    """Run a lifecycle action (`publish`, `archive`, `cancel` ...) and check the status."""
    response = client.post(f"/api/events/{eid}/{action}", json=body, headers=etag(client, eid))
    return expect(response, status, f"{action} -> {status}")


def patch(client: httpx.Client, eid: str, **fields: object) -> dict:
    """Change base data of a dossier with the current version."""
    return expect(
        client.patch(f"/api/events/{eid}", json=fields, headers=etag(client, eid)),
        200,
        f"patch {sorted(fields)}",
    )


def published(client: httpx.Client, title: str, *, days: int = 30, category: str = "kino") -> str:
    """Create a dossier of the FSI, confirm its venue and publish it; return its id."""
    eid = create(client, title, category=category, days=days)
    confirm_location(client, eid)
    act(client, eid, "publish")
    return eid


def archived(client: httpx.Client, title: str, *, days: int = 30) -> str:
    """Create, publish and archive a dossier of the FSI; return its id."""
    eid = published(client, title, days=days)
    act(client, eid, "archive")
    return eid
