"""Every route of the public routers reads through the public session, and no module there imports a table."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.ics_router import router as ics_router
from app.modules.publicapi.router import router as feed_router
from app.modules.publicapi.shell.router import router as shell_router
from app.modules.publicapi.site_router import router as site_router

ROOT = Path(__file__).resolve().parents[3] / "app" / "modules" / "publicapi"
FORBIDDEN_NAMES = {"get_session", "DbSession", "Event", "Attachment"}
ROUTES = [
    (router, route)
    for router in (site_router, ics_router, shell_router, feed_router)
    for route in router.routes
    if isinstance(route, APIRoute)
]


def calls(dependant: Dependant) -> list[object]:
    return [dependant.call] + [c for child in dependant.dependencies for c in calls(child)]


@pytest.mark.parametrize("route", [r for _, r in ROUTES], ids=lambda r: r.path)
def test_a_public_route_uses_the_public_session_and_never_the_application_session(
    route: APIRoute,
) -> None:
    used = calls(route.dependant)
    assert get_public_session in used
    names = {getattr(call, "__name__", "") for call in used}
    assert not names & {"get_session", "get_current_principal", "require_principal"}


def test_no_public_module_imports_a_model_or_the_application_session() -> None:
    offenders = []
    for source in sorted(ROOT.rglob("*.py")):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                bad_module = node.module.endswith(".models") or node.module in {
                    "app.db",
                    "app.deps",
                }
                bad_name = any(alias.name in FORBIDDEN_NAMES for alias in node.names)
                if bad_module or bad_name:
                    offenders.append((str(source.relative_to(ROOT)), node.module))
    assert not offenders, offenders
