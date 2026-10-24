"""The real local Listmonk for the opt-in tests: admin login, a throwaway API user and cleanup.

`make_real` skips the test when no Listmonk answers on `LISTMONK_TEST_URL`. Everything it creates
(role, API user, and the lists, campaigns and subscribers a test registers in `made`) is deleted by
`cleanup`.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
import pytest

from app.modules.subscriptions.listmonk_client import ListmonkClient
from app.modules.subscriptions.listmonk_port import ListmonkPort

URL = os.environ.get("LISTMONK_TEST_URL", "http://127.0.0.1:9002")
ADMIN = (
    os.environ.get("LISTMONK_ADMIN_USER", "admin"),
    os.environ.get("LISTMONK_ADMIN_PASSWORD", "dev-listmonk-admin"),
)
MAILPIT = os.environ.get("MAILPIT_URL", "http://127.0.0.1:8025")


@dataclass
class Harness:
    """A port plus the out-of-band actions of a person inside Listmonk."""

    port: ListmonkPort
    unsubscribe: Callable[[str, int], None]
    cleanup: Callable[[], None]
    made: dict[str, list[int]] = field(
        default_factory=lambda: {"lists": [], "campaigns": [], "subscribers": []}
    )


def admin_session() -> httpx.Client:
    http = httpx.Client(base_url=URL, follow_redirects=False)
    nonce = re.search(r'name="nonce" value="([^"]*)"', http.get("/admin/login").text)
    assert nonce
    http.post(
        "/admin/login",
        data={
            "nonce": nonce.group(1),
            "next": "/admin",
            "username": ADMIN[0],
            "password": ADMIN[1],
        },
    )
    return http


def make_real() -> tuple[Harness, ListmonkClient]:
    try:
        admin = admin_session()
        admin.get("/api/users").raise_for_status()
    except (httpx.HTTPError, AssertionError) as exc:
        pytest.skip(f"no local Listmonk: {type(exc).__name__}")
    name = f"contract-{uuid.uuid4().hex[:8]}"
    role = {
        "name": name,
        "permissions": [
            "subscribers:get",
            "subscribers:get_all",
            "subscribers:manage",
            "campaigns:get",
            "campaigns:get_all",
            "campaigns:manage",
            "campaigns:manage_all",
            "lists:get_all",
            "lists:manage_all",
        ],
    }
    role_id = admin.post("/api/roles/users", json=role).json()["data"]["id"]
    user = admin.post(
        "/api/users",
        json={
            "username": name,
            "name": name,
            "type": "api",
            "status": "enabled",
            "user_role_id": role_id,
            "list_role_id": None,
        },
    ).json()["data"]
    client = ListmonkClient(URL, name, user["password"])
    api = httpx.Client(base_url=URL, headers={"Authorization": f"token {name}:{user['password']}"})

    def unsubscribe(email: str, list_id: int) -> None:
        found = api.get("/api/subscribers", params={"search": email})
        sid = found.json()["data"]["results"][0]["id"]
        api.put(
            "/api/subscribers/lists",
            json={"ids": [sid], "action": "unsubscribe", "target_list_ids": [list_id]},
        )

    def cleanup() -> None:
        for sid in made["subscribers"]:
            api.delete(f"/api/subscribers/{sid}")
        for cid in made["campaigns"]:
            api.delete(f"/api/campaigns/{cid}")
        for lid in made["lists"]:
            api.delete(f"/api/lists/{lid}")
        admin.delete(f"/api/users/{user['id']}")
        admin.delete(f"/api/roles/{role_id}")

    harness = Harness(client, unsubscribe, cleanup)
    made = harness.made
    return harness, client
