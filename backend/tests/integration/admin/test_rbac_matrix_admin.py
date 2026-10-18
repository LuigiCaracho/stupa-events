"""Every route of the inventory x every test user, generated (PLAN 5.5, contract M2 6.2).

The expectation comes from the permission catalogue and the role table of each user, not
from the gate code: a route whose gate passes answers anything but 401, 403 and 5xx, a route
whose gate fails answers exactly 403, and without a session every route answers 401.
"""

from __future__ import annotations

import re

import pytest

from app.shared.permissions import permissions_of
from tests.integration.events.harness import Api
from tests.unit.test_route_authz_inventory import (
    PUBLIC_ALLOWLIST,
    PUBLIC_PREFIX,
    ROUTE_PERMS,
    _calls,
    _routes,
)

pytestmark = pytest.mark.integration

ZERO = "00000000-0000-0000-0000-000000000000"
# user: (global roles, organization roles as they resolve, trusted approver included)
ROLES: dict[str, tuple[set[str], set[str]]] = {
    "admin": ({"admin"}, set()),
    "editor": ({"editor"}, set()),
    "stupa": ({"stupa"}, set()),
    "approver-stupa": (set(), {"approver"}),
    "approver-fsi": (set(), {"organizer"}),
    "organizer-fsi": (set(), {"organizer"}),
    "submitter-fsi": (set(), {"submitter"}),
    "viewer-fsi": (set(), {"viewer"}),
    "organizer-makers": (set(), {"organizer"}),
    "submitter-ekhg": (set(), {"submitter"}),
    "member": (set(), set()),
    "nobody": (set(), set()),
}


def _gate_kind(route: object) -> str:
    gates = [c for c in _calls(route.dependant) if getattr(c, "authz_gate", False)]  # type: ignore[attr-defined]
    return gates[0].__qualname__.split(".")[0]


def _holds(user: str, kind: str, perms: frozenset[str]) -> bool:
    global_roles, org_roles = ROLES[user]
    if "admin" in global_roles:
        return True
    held = permissions_of({"member", *global_roles})
    in_orgs = permissions_of(org_roles)
    if kind == "require_principal":
        return all(p in held for p in perms)
    if kind == "require_any_permission":
        return any(p in held for p in perms)
    return any(p in held or p in in_orgs for p in perms)


def _protected() -> list[tuple[str, str, str, frozenset[str]]]:
    return [
        (method, path, _gate_kind(route), ROUTE_PERMS[(method, path)])
        for method, path, route in _routes()
        if (method, path) not in PUBLIC_ALLOWLIST and not path.startswith(PUBLIC_PREFIX)
    ]


def _url(path: str) -> str:
    return re.sub(r"\{transition\}", "T01", re.sub(r"\{[a-z_]+\}", ZERO, path))


async def _call(api: Api, user: str | None, method: str, path: str) -> int:
    kwargs = {} if method == "GET" else {"json": {}}
    return (await api.request(user, method, _url(path), **kwargs)).status_code


async def test_every_route_without_a_session_is_401(api: Api) -> None:
    wrong = {
        f"{m} {p}": status
        for m, p, _, _ in _protected()
        if (status := await _call(api, None, m, p)) != 401
    }
    assert not wrong


@pytest.mark.parametrize("user", ROLES)
async def test_every_route_by_user_follows_the_catalogue(api: Api, user: str) -> None:
    wrong: dict[str, tuple[int, bool]] = {}
    for method, path, kind, perms in _protected():
        status = await _call(api, user, method, path)
        expected = _holds(user, kind, perms)
        if (status == 403) == expected or status == 401 or (expected and status >= 500):
            wrong[f"{method} {path}"] = (status, expected)
    assert not wrong


async def test_the_matrix_covers_every_admin_route() -> None:
    admin_routes = {(m, p) for m, p, _, _ in _protected() if p.startswith("/api/admin/")}
    assert len(admin_routes) >= 18


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/api/admin/organizations", {"admin", "editor"}),
        ("/api/admin/categories", {"admin", "editor"}),
        ("/api/admin/venues", {"admin", "editor"}),
        ("/api/admin/group-mappings", {"admin"}),
        ("/api/admin/principals", {"admin"}),
        ("/api/admin/audit", {"admin"}),
    ],
)
async def test_admin_lists_answer_200_for_the_right_roles_only(
    api: Api, path: str, allowed: set[str]
) -> None:
    for user in ROLES:
        status = await api.request(user, "GET", path)
        assert status.status_code == (200 if user in allowed else 403), (user, path)


async def test_session_routes_and_reference_lists(api: Api) -> None:
    for user in ROLES:
        for path in ("/api/organizations", "/api/categories", "/api/venues", "/api/auth/me"):
            assert (await api.request(user, "GET", path)).status_code == 200, (user, path)
        revoke = await api.request(user, "POST", "/api/auth/sessions/revoke", json={})
        assert revoke.status_code == 200, user
    assert (
        await api.request(None, "POST", "/api/auth/sessions/revoke", json={})
    ).status_code == 401


async def test_only_the_admin_may_end_sessions_of_others(api: Api) -> None:
    for user in ROLES:
        status = await api.request(
            user, "POST", f"/api/admin/principals/{ZERO}/sessions/revoke", json={}
        )
        assert status.status_code == (404 if user == "admin" else 403), user
