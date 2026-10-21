"""Helpers of the dossier integration tests: uploads, ready posters and published dossiers."""

from __future__ import annotations

import json
from typing import Any

from httpx import Response

from tests._support.factories import png_bytes
from tests.integration.events.harness import Api

MIME = {"png": "image/png", "pdf": "application/pdf", "jpg": "image/jpeg"}


async def upload(
    api: Api,
    user: str,
    event_id: str,
    kind: str,
    name: str,
    data: bytes,
    **form: str,
) -> Response:
    """Upload `data` as an attachment of `kind` through the generic route."""
    mime = MIME.get(name.rsplit(".", 1)[-1], "application/octet-stream")
    return await api.request(
        user,
        "POST",
        f"/api/events/{event_id}/attachments",
        data={"kind": kind, **form},
        files={"file": (name, data, mime)},
    )


async def draft_event(api: Api, user: str = "organizer-fsi", **over: Any) -> str:
    """Create a dossier in `draft`; return its id."""
    return (await api.create_event(user=user, **over))["id"]


async def clean_poster(api: Api, event_id: str, user: str = "organizer-fsi") -> dict:
    """Upload a poster, scan and derive it; return the attachment."""
    out = await api.upload_poster(user, event_id, data=png_bytes())
    assert out.status_code == 201, out.text
    assert await api.process_poster(out.json()["id"]) == "clean"
    return out.json()


async def published_event(api: Api) -> dict:
    """A published dossier with a clean poster."""
    event = await api.create_event()
    await api.with_poster(event["id"])
    await api.confirm_location(event["id"])
    assert (await api.act("organizer-fsi", event["id"], "publish")).status_code == 200
    return await api.get("editor", event["id"])


async def seed_principals(api: Api) -> None:
    """Persist the test users as `principal` and `membership` rows (the login sync does it live)."""
    for name, (sub, groups) in api.users.items():
        await api.sql(
            "INSERT INTO principal (sub, email, display_name, oidc_groups) "
            "VALUES (:sub, :email, :name, CAST(:groups AS jsonb)) ON CONFLICT DO NOTHING",
            sub=sub,
            email=f"{name}@example.org",
            name=name.replace("-", " ").title(),
            groups=json.dumps(list(groups)),
        )
        for group in groups:
            parts = group.removeprefix("events-").rsplit("-", 1)
            if len(parts) == 2:
                await api.sql(
                    "INSERT INTO membership (principal_id, organization_id, role) "
                    "SELECT p.id, o.id, :role FROM principal p, organization o "
                    "WHERE p.sub = :sub AND o.slug = :slug ON CONFLICT DO NOTHING",
                    sub=sub,
                    slug=parts[0],
                    role=parts[1],
                )
