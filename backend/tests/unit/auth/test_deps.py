"""Dependencies: session resolution and the 401/403 gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app import deps
from app.db import get_session
from app.main import create_app
from app.modules.auth import rbac, sessions
from app.settings import get_settings
from tests._support.auth_fakes import fake_session, result
from tests._support.factories import make_principal, make_settings

SECRET = "test-session-secret"


def _request(cookie: str | None) -> Any:
    return SimpleNamespace(cookies={"ev_session": cookie} if cookie else {})


def _row(active: bool = True) -> Any:
    return SimpleNamespace(id="pid", active=active, sub="s")


def _session_row() -> Any:
    return SimpleNamespace(
        sid="sid-1", principal_id="pid", expires_at=datetime.now(UTC) + timedelta(days=1)
    )


@pytest.fixture
def renewal(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    state = {"keep": True}

    async def fake(*args: Any, **kwargs: Any) -> bool:
        return state["keep"]

    async def resolve(db: Any, row: Any, settings: Any) -> Any:
        return make_principal("events-editor", sub=row.sub)

    monkeypatch.setattr(deps, "renew_principal_session", fake)
    monkeypatch.setattr(rbac, "resolve_principal", resolve)
    return state


async def _resolve(db: Any, cookie: str | None) -> Any:
    return await deps.get_current_principal(_request(cookie), db, make_settings())


def _cookie() -> str:
    return sessions.sign_principal_sid(SECRET, "sid-1")


async def test_no_cookie_and_bad_cookie_resolve_to_none(renewal: dict[str, bool]) -> None:
    assert await _resolve(fake_session(), None) is None
    assert await _resolve(fake_session(), "forged") is None


async def test_valid_session_resolves_the_principal(renewal: dict[str, bool]) -> None:
    db = fake_session(result(_session_row()), result(_row()))
    principal = await _resolve(db, _cookie())
    assert principal is not None and principal.sub == "s"


async def test_unknown_session_or_inactive_or_ended_session_is_anonymous(
    renewal: dict[str, bool],
) -> None:
    assert await _resolve(fake_session(result()), _cookie()) is None
    assert await _resolve(fake_session(result(_session_row()), result()), _cookie()) is None
    inactive = fake_session(result(_session_row()), result(_row(active=False)))
    assert await _resolve(inactive, _cookie()) is None
    renewal["keep"] = False
    ended = fake_session(result(_session_row()), result(_row()))
    assert await _resolve(ended, _cookie()) is None


async def test_deactivated_during_renewal_is_anonymous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _row()

    async def renew(*args: Any, **kwargs: Any) -> bool:
        row.active = False
        return True

    monkeypatch.setattr(deps, "renew_principal_session", renew)
    db = fake_session(result(_session_row()), result(row))
    assert await _resolve(db, _cookie()) is None


@pytest.fixture
def gated() -> TestClient:
    app = create_app(make_settings())
    principal = make_principal("events-fsi-submitter")

    async def _db():
        yield fake_session()

    app.dependency_overrides[get_session] = _db
    app.dependency_overrides[get_settings] = lambda: make_settings()
    router = APIRouter()

    @router.get("/g/perm", dependencies=[Depends(deps.require_principal("event.submit"))])
    def perm() -> str:
        return "ok"

    @router.get("/g/any", dependencies=[Depends(deps.require_any_permission("event.approve", "x"))])
    def any_perm() -> str:
        return "ok"

    @router.get("/g/scope", dependencies=[Depends(deps.require_any_scope("event.create"))])
    def scope() -> str:
        return "ok"

    @router.get("/g/scope-no", dependencies=[Depends(deps.require_any_scope("event.submit"))])
    def scope_no() -> str:
        return "ok"

    @router.get("/g/group", dependencies=[Depends(deps.require_group("events-fsi-submitter"))])
    def group() -> str:
        return "ok"

    @router.get("/g/group-no", dependencies=[Depends(deps.require_group("other"))])
    def group_no() -> str:
        return "ok"

    @router.get("/g/open", dependencies=[Depends(deps.require_principal())])
    def open_() -> str:
        return "ok"

    app.include_router(router)
    client = TestClient(app)
    client.app.dependency_overrides[deps.get_current_principal] = lambda: principal  # type: ignore[attr-defined]
    return client


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/g/perm", 403),
        ("/g/any", 403),
        ("/g/scope", 200),
        ("/g/scope-no", 403),
        ("/g/group", 200),
        ("/g/group-no", 403),
        ("/g/open", 200),
    ],
)
def test_gates_for_an_org_submitter(gated: TestClient, path: str, status: int) -> None:
    assert gated.get(path).status_code == status


@pytest.mark.parametrize("path", ["/g/perm", "/g/any", "/g/scope", "/g/group", "/g/open"])
def test_every_gate_answers_401_without_a_session(path: str) -> None:
    app = create_app(make_settings())
    router = APIRouter()
    gates = {
        "/g/perm": deps.require_principal("event.submit"),
        "/g/any": deps.require_any_permission("event.submit"),
        "/g/scope": deps.require_any_scope("event.create"),
        "/g/group": deps.require_group("g"),
        "/g/open": deps.require_principal(),
    }
    router.add_api_route(path, lambda: "ok", dependencies=[Depends(gates[path])])
    app.include_router(router)
    app.dependency_overrides[deps.get_current_principal] = lambda: None
    response = TestClient(app).get(path)
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
