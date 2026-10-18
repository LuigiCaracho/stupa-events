"""Every route declares an authorization gate or sits in the public allowlist.

A route without `require_principal`, `require_any_permission`, `require_any_scope` or
`require_group` fails here, so a forgotten gate breaks CI instead of shipping.
"""

from __future__ import annotations

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.api_routers import ROUTERS
from app.main import api_router

PUBLIC_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/api/health"),
        ("GET", "/api/auth/login"),
        ("GET", "/api/auth/callback"),
        ("POST", "/api/auth/logout"),
    }
)
PUBLIC_PREFIX = "/api/public/"
FORBIDDEN_PUBLIC_DEPENDENCIES = frozenset({"get_session", "get_current_principal"})
EXPECTED_GATE_PERMS: dict[tuple[str, str], frozenset[str]] = {
    ("POST", "/api/events/{event_id}/transitions/{transition}"): frozenset(
        {"event.edit", "event.submit", "event.approve"}
    ),
    ("GET", "/api/events/{event_id}/guards/{transition}"): frozenset(
        {"event.edit", "event.submit", "event.approve"}
    ),
    ("POST", "/api/events/{event_id}/image-exception"): frozenset({"event.image_exception"}),
}


def _gated(dependant: Dependant) -> bool:
    if getattr(dependant.call, "authz_gate", False):
        return True
    return any(_gated(child) for child in dependant.dependencies)


def _calls(dependant: Dependant) -> list[object]:
    return [dependant.call] + [c for child in dependant.dependencies for c in _calls(child)]


def _gate_perms(dependant: Dependant) -> frozenset[str]:
    return frozenset(p for call in _calls(dependant) for p in getattr(call, "authz_perms", ()))


def _routes() -> list[tuple[str, str, APIRoute]]:
    """List `(method, path, route)` of the own routers; module routers get `/api`."""
    own = [(r, "") for r in api_router.routes] + [
        (route, "/api") for router in ROUTERS for route in router.routes
    ]
    return [
        (method, f"{prefix}{route.path}", route)
        for route, prefix in own
        if isinstance(route, APIRoute)
        for method in sorted(route.methods or ())
    ]


def test_every_route_is_gated_or_explicitly_public() -> None:
    ungated = [
        f"{method} {path}"
        for method, path, route in _routes()
        if (method, path) not in PUBLIC_ALLOWLIST
        and not path.startswith(PUBLIC_PREFIX)
        and not _gated(route.dependant)
    ]
    assert not ungated, f"routes without an authorization gate: {ungated}"


def test_the_allowlist_holds_no_stale_entries() -> None:
    existing = {(method, path) for method, path, _ in _routes()}
    assert existing >= PUBLIC_ALLOWLIST


def test_me_and_the_audit_routes_are_gated() -> None:
    gated = {f"{m} {p}" for m, p, r in _routes() if _gated(r.dependant)}
    assert "GET /api/auth/me" in gated
    assert "GET /api/admin/audit" in gated


def test_pipeline_routes_carry_their_permission_gate() -> None:
    gates = {(m, p): _gate_perms(r.dependant) for m, p, r in _routes()}
    wrong = {
        key: gates.get(key) for key, want in EXPECTED_GATE_PERMS.items() if gates.get(key) != want
    }
    assert not wrong, f"unexpected gate permissions: {wrong}"


def test_public_routes_use_only_the_public_session() -> None:
    offenders = [
        f"{method} {path}"
        for method, path, route in _routes()
        if path.startswith(PUBLIC_PREFIX)
        and any(
            getattr(call, "__name__", "") in FORBIDDEN_PUBLIC_DEPENDENCIES
            for call in _calls(route.dependant)
        )
    ]
    assert not offenders, f"public routes with an application session: {offenders}"
