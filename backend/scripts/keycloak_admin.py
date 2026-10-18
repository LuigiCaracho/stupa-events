"""Keycloak admin API of the local dev IdP: sync the realm file and move users between groups.

Only for the dev stack (`admin`/`admin` on `localhost:8090`). The realm import runs only
when the realm does not exist yet, so a Keycloak that predates a change of
`deploy/keycloak/stupa-events-realm.json` needs `sync_realm_users` once.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

KEYCLOAK = os.environ.get("KEYCLOAK_URL", "http://localhost:8090")
REALM = "stupa-events"
REALM_FILE = Path(__file__).resolve().parents[2] / "deploy" / "keycloak" / "stupa-events-realm.json"


class Keycloak:
    """A small client of the admin REST API of the realm."""

    def __init__(self) -> None:
        self.http = httpx.Client(base_url=KEYCLOAK, timeout=20.0)
        token = self.http.post(
            "/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin",
            },
        ).json()["access_token"]
        self.http.headers["Authorization"] = f"Bearer {token}"

    def _admin(self, path: str) -> str:
        return f"/admin/realms/{REALM}{path}"

    def group_id(self, name: str) -> str | None:
        """Return the id of the group `name`, or `None`."""
        groups = self.http.get(
            self._admin("/groups"), params={"search": name, "exact": "true"}
        ).json()
        return next((g["id"] for g in groups if g["name"] == name), None)

    def user_id(self, username: str) -> str | None:
        """Return the id of the user `username`, or `None`."""
        users = self.http.get(
            self._admin("/users"), params={"username": username, "exact": "true"}
        ).json()
        return users[0]["id"] if users else None

    def set_membership(self, username: str, group: str, *, member: bool) -> None:
        """Put the user into the group or take them out."""
        user, gid = self.user_id(username), self.group_id(group)
        assert user and gid, f"unknown user {username} or group {group}"
        url = self._admin(f"/users/{user}/groups/{gid}")
        (self.http.put if member else self.http.delete)(url).raise_for_status()

    def sync_realm_users(self) -> int:
        """Create the groups and users of the realm file that are missing; return their count.

        It also puts every user into the groups the file names, which undoes an earlier run.
        """
        realm = json.loads(REALM_FILE.read_text(encoding="utf-8"))
        created = 0
        for group in realm["groups"]:
            if self.group_id(group["name"]) is None:
                self.http.post(
                    self._admin("/groups"), json={"name": group["name"]}
                ).raise_for_status()
                created += 1
        for user in realm["users"]:
            if self.user_id(user["username"]) is None:
                body = {k: v for k, v in user.items() if k not in {"groups", "realmRoles"}}
                self.http.post(self._admin("/users"), json=body).raise_for_status()
                created += 1
            for path in user["groups"]:
                self.set_membership(user["username"], path.lstrip("/"), member=True)
        return created
