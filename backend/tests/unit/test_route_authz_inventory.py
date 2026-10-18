"""Every route declares an authorization gate with its permission set, or is public (PLAN 5.5).

`ROUTE_PERMS` lists each non-public route with the permissions of its gate. A new route
that nobody lists fails here, a removed route with a stale entry fails too, and a gate
without a permission is allowed only for the two session routes in
`SESSION_ONLY_ALLOWLIST`. The meta tests prove that the check itself finds an open route.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter, Depends
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.api_routers import ROUTERS
from app.deps import require_principal
from app.main import api_router

Route = tuple[str, str, APIRoute]

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
SESSION_ONLY_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {("GET", "/api/auth/me"), ("POST", "/api/auth/sessions/revoke")}
)
_TRANSITION = frozenset({"event.edit", "event.submit", "event.approve"})
_READ = frozenset({"library.read"})
_MAPPINGS = frozenset({"admin.mappings"})
_TAXONOMY = frozenset({"taxonomy.manage"})
ROUTE_PERMS: dict[tuple[str, str], frozenset[str]] = {
    ("GET", "/api/admin/audit"): frozenset({"audit.read"}),
    ("GET", "/api/admin/audit/verify"): frozenset({"audit.verify"}),
    ("POST", "/api/admin/audit/verify"): frozenset({"audit.verify"}),
    ("GET", "/api/admin/audit/verify/latest"): frozenset({"audit.read"}),
    ("GET", "/api/admin/group-mappings"): _MAPPINGS,
    ("POST", "/api/admin/group-mappings"): _MAPPINGS,
    ("POST", "/api/admin/group-mappings/defaults"): _MAPPINGS,
    ("PATCH", "/api/admin/group-mappings/{mapping_id}"): _MAPPINGS,
    ("DELETE", "/api/admin/group-mappings/{mapping_id}"): _MAPPINGS,
    ("GET", "/api/admin/principals"): frozenset({"admin.mappings", "admin.sessions.revoke"}),
    ("POST", "/api/admin/principals/{principal_id}/sessions/revoke"): frozenset(
        {"admin.sessions.revoke"}
    ),
    ("GET", "/api/admin/organizations"): _TAXONOMY,
    ("POST", "/api/admin/organizations"): _TAXONOMY,
    ("PATCH", "/api/admin/organizations/{organization_id}"): _TAXONOMY,
    ("GET", "/api/admin/categories"): _TAXONOMY,
    ("POST", "/api/admin/categories"): _TAXONOMY,
    ("PATCH", "/api/admin/categories/{category_id}"): _TAXONOMY,
    ("GET", "/api/admin/venues"): frozenset({"venue.manage"}),
    ("POST", "/api/admin/venues"): frozenset({"venue.manage"}),
    ("PATCH", "/api/admin/venues/{venue_id}"): frozenset({"venue.manage"}),
    ("GET", "/api/organizations"): _READ,
    ("GET", "/api/categories"): _READ,
    ("GET", "/api/venues"): _READ,
    ("GET", "/api/events"): _READ,
    ("POST", "/api/events"): frozenset({"event.create"}),
    ("GET", "/api/events/{event_id}"): _READ,
    ("PATCH", "/api/events/{event_id}"): frozenset({"event.edit"}),
    ("POST", "/api/events/{event_id}/transitions/{transition}"): _TRANSITION,
    ("GET", "/api/events/{event_id}/guards/{transition}"): _TRANSITION,
    ("POST", "/api/events/{event_id}/image-exception"): frozenset({"event.image_exception"}),
    ("POST", "/api/events/{event_id}/poster"): frozenset({"dossier.attach"}),
    ("GET", "/api/events/{event_id}/poster/file"): _READ,
    ("GET", "/api/auth/me"): frozenset(),
    ("POST", "/api/auth/sessions/revoke"): frozenset(),
}


def _gated(dependant: Dependant) -> bool:
    if getattr(dependant.call, "authz_gate", False):
        return True
    return any(_gated(child) for child in dependant.dependencies)


def _calls(dependant: Dependant) -> list[object]:
    return [dependant.call] + [c for child in dependant.dependencies for c in _calls(child)]


def _gate_perms(dependant: Dependant) -> frozenset[str]:
    return frozenset(p for call in _calls(dependant) for p in getattr(call, "authz_perms", ()))


def flatten(router: APIRouter, prefix: str = "") -> Iterable[Route]:
    """Yield `(method, path, route)` of a router, following nested `include_router` calls."""
    for route in router.routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from flatten(nested, prefix + route.include_context.prefix)  # type: ignore[attr-defined]
        elif isinstance(route, APIRoute):
            for method in sorted(route.methods or ()):
                yield method, f"{prefix}{route.path}", route


def _routes() -> list[Route]:
    """List the routes of the app: the own `/api` router and every module router."""
    found = list(flatten(api_router)) + [r for router in ROUTERS for r in flatten(router, "/api")]
    return list({(method, path): (method, path, route) for method, path, route in found}.values())


def open_routes(routes: Iterable[Route]) -> list[str]:
    """Name the non-public routes without a gate, or with a permission-less gate off the list."""
    problems = []
    for method, path, route in routes:
        if (method, path) in PUBLIC_ALLOWLIST or path.startswith(PUBLIC_PREFIX):
            continue
        if not _gated(route.dependant):
            problems.append(f"{method} {path}: no gate")
        elif not _gate_perms(route.dependant) and (method, path) not in SESSION_ONLY_ALLOWLIST:
            problems.append(f"{method} {path}: gate without a permission")
    return problems


def test_every_route_is_gated_or_explicitly_public() -> None:
    assert not open_routes(_routes())


def test_the_allowlists_hold_no_stale_entries() -> None:
    existing = {(method, path) for method, path, _ in _routes()}
    assert existing >= PUBLIC_ALLOWLIST | SESSION_ONLY_ALLOWLIST


def test_every_route_has_an_expected_permission_set() -> None:
    gates = {
        (m, p): _gate_perms(r.dependant)
        for m, p, r in _routes()
        if (m, p) not in PUBLIC_ALLOWLIST and not p.startswith(PUBLIC_PREFIX)
    }
    assert set(gates) == set(ROUTE_PERMS), {
        "unlisted": sorted(set(gates) - set(ROUTE_PERMS)),
        "stale": sorted(set(ROUTE_PERMS) - set(gates)),
    }
    wrong = {k: (gates[k], want) for k, want in ROUTE_PERMS.items() if gates[k] != want}
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


def test_the_check_finds_an_unprotected_and_a_permissionless_route() -> None:
    probe = APIRouter(prefix="/probe")

    @probe.get("/open")
    def open_route() -> dict[str, str]:
        return {}

    @probe.get("/blank", dependencies=[Depends(require_principal())])
    def blank_route() -> dict[str, str]:
        return {}

    @probe.get("/read", dependencies=[Depends(require_principal("library.read"))])
    def read_route() -> dict[str, str]:
        return {}

    assert open_routes(flatten(probe, "/api")) == [
        "GET /api/probe/open: no gate",
        "GET /api/probe/blank: gate without a permission",
    ]


def test_the_inventory_follows_nested_routers() -> None:
    inner, outer = APIRouter(prefix="/inner"), APIRouter(prefix="/outer")

    @inner.get("/hidden")
    def hidden() -> dict[str, str]:
        return {}

    outer.include_router(inner)
    assert open_routes(flatten(outer)) == ["GET /outer/inner/hidden: no gate"]
