"""Inbox, unread count, read marks and account settings over HTTP (real app, real DB)."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.notifications.service import notify
from tests.integration.events.harness import Api
from tests.integration.notifications.conftest import add_principal, load_event

pytestmark = pytest.mark.integration


async def _seed(api: Api, count: int = 3, sub: str = "sub-editor") -> dict:
    event = await api.create_event()
    async with api.maker() as session:
        row = await load_event(session, event["id"])
        await add_principal(session, sub)
        for i in range(count):
            await notify(session, "comment_added", [sub], row, {"actorName": "Ada"}, f"seed:{i}")
        await session.commit()
    return event


async def test_notifications_api(api: Api) -> None:
    event = await _seed(api)
    listing = (await api.request("editor", "GET", "/api/notifications")).json()
    assert len(listing["items"]) == 3
    first = listing["items"][0]
    assert first["kind"] == "comment_added"
    assert first["eventTitle"] == event["title"]
    assert first["link"] == f"/dossiers/{event['id']}/verlauf"
    assert first["readAt"] is None
    count = (await api.request("editor", "GET", "/api/notifications/unread-count")).json()
    assert count == {"count": 3}

    assert (
        await api.request("editor", "POST", f"/api/notifications/{first['id']}/read")
    ).status_code == 204
    assert (await api.request("editor", "GET", "/api/notifications/unread-count")).json()[
        "count"
    ] == 2
    assert (
        await api.request("organizer-fsi", "POST", f"/api/notifications/{first['id']}/read")
    ).status_code == 404
    unread = (await api.request("editor", "GET", "/api/notifications?unread=true")).json()
    assert len(unread["items"]) == 2
    assert (await api.request("editor", "POST", "/api/notifications/read-all")).status_code == 204
    assert (await api.request("editor", "GET", "/api/notifications/unread-count")).json()[
        "count"
    ] == 0
    assert (await api.request(None, "GET", "/api/notifications")).status_code == 401


async def test_inbox_paging_and_isolation(api: Api) -> None:
    await _seed(api, count=5)
    first = (await api.request("editor", "GET", "/api/notifications?limit=2")).json()
    assert len(first["items"]) == 2 and first["nextCursor"]
    second = (
        await api.request(
            "editor", "GET", f"/api/notifications?limit=2&cursor={first['nextCursor']}"
        )
    ).json()
    ids = [i["id"] for i in first["items"] + second["items"]]
    assert len(set(ids)) == 4
    other = (await api.request("organizer-fsi", "GET", "/api/notifications")).json()
    assert other["items"] == []
    bad = await api.request("editor", "GET", "/api/notifications?cursor=%21%21")
    assert bad.status_code == 400


async def test_dedupe_key_blocks_double_rows(api: Api) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        row = await load_event(session, event["id"])
        await add_principal(session, "sub-editor")
        for _ in range(2):
            await notify(session, "task_assigned", ["sub-editor"], row, {}, "once")
        await session.commit()
    assert (await api.request("editor", "GET", "/api/notifications/unread-count")).json()[
        "count"
    ] == 1


async def test_prefs_api(api: Api) -> None:
    got = (await api.request("editor", "GET", "/api/account/notification-prefs")).json()
    assert len(got["items"]) == 7
    assert all(i["inApp"] and i["mail"] == i["mailAvailable"] for i in got["items"])
    assert [i["kind"] for i in got["items"] if i["essential"]] == ["changes_requested"]

    put: Any = await api.request(
        "editor",
        "PUT",
        "/api/account/notification-prefs",
        json={"items": [{"kind": "comment_added", "inApp": False, "mail": False}]},
    )
    assert put.status_code == 200
    by_kind = {i["kind"]: i for i in put.json()["items"]}
    assert by_kind["comment_added"]["inApp"] is False
    assert by_kind["task_assigned"]["inApp"] is True

    essential = await api.request(
        "editor",
        "PUT",
        "/api/account/notification-prefs",
        json={"items": [{"kind": "changes_requested", "inApp": True, "mail": False}]},
    )
    assert essential.status_code == 422
    assert essential.json()["code"] == "kind_essential"
    unknown = await api.request(
        "editor",
        "PUT",
        "/api/account/notification-prefs",
        json={"items": [{"kind": "nope", "inApp": True, "mail": True}]},
    )
    assert unknown.status_code == 422
    extra = await api.request(
        "editor", "PUT", "/api/account/notification-prefs", json={"items": [], "x": 1}
    )
    assert extra.status_code == 422


async def test_pref_off_skips_inbox_row(api: Api) -> None:
    event = await api.create_event()
    await api.request(
        "editor",
        "PUT",
        "/api/account/notification-prefs",
        json={"items": [{"kind": "comment_added", "inApp": False, "mail": True}]},
    )
    async with api.maker() as session:
        row = await load_event(session, event["id"])
        await add_principal(session, "sub-editor")
        pending = await notify(session, "comment_added", ["sub-editor"], row, {}, None)
        await session.commit()
    assert (await api.request("editor", "GET", "/api/notifications/unread-count")).json()[
        "count"
    ] == 0
    assert len(pending) == 1
    assert (await api.sql("SELECT count(*) FROM notification"))[0][0] == 0
