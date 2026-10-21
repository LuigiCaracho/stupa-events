"""Auth routes with a fake database: login redirect, callback, logout and `/auth/me`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.deps import get_current_principal
from app.main import create_app
from app.modules.auth import oidc, service, sessions
from app.modules.auth.oidc import OidcError, OidcUnavailableError
from app.settings import get_settings
from tests._support.auth_fakes import fake_session, result
from tests._support.factories import make_principal, make_settings

SECRET = "test-session-secret"
FSI_ID = uuid4()


def _oidc_settings() -> Any:
    return make_settings(
        oidc_issuer="http://idp/realms/x",
        oidc_client_id="events",
        oidc_client_secret="s" * 16,
        oidc_redirect_url="http://localhost/api/auth/callback",
        cookie_secure=False,
    )


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, dict[str, Any]]]:
    app = create_app(make_settings())
    state: dict[str, Any] = {"db": fake_session(), "settings": _oidc_settings()}

    async def _db():
        yield state["db"]

    app.dependency_overrides[get_session] = _db
    app.dependency_overrides[get_settings] = lambda: state["settings"]
    yield TestClient(app, follow_redirects=False), state


def _tx_cookie(client: str = "web", return_to: str | None = "/events") -> str:
    return sessions.issue_oidc_tx(SECRET, "st", "ver", "non", client, return_to)


def test_login_redirects_to_the_idp_and_sets_the_tx_cookie(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = app_client

    async def fake_url(settings: Any, **kwargs: Any) -> str:
        return f"http://idp/auth?state={kwargs['state']}"

    monkeypatch.setattr(oidc, "authorization_url", fake_url)
    response = client.get("/api/auth/login?client=pwa&returnTo=/events")
    assert response.status_code == 307
    assert response.headers["location"].startswith("http://idp/auth?state=")
    cookie = response.cookies["ev_oidc_tx"]
    tx = sessions.load_oidc_tx(SECRET, cookie, 600)
    assert tx is not None and tx["client"] == "pwa" and tx["return_to"] == "/events"


def test_login_503_when_the_idp_is_down(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*args: Any, **kwargs: Any) -> str:
        raise OidcUnavailableError("down")

    monkeypatch.setattr(oidc, "authorization_url", boom)
    assert app_client[0].get("/api/auth/login").status_code == 503


def test_callback_opens_the_session_and_returns_to_the_path(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = app_client

    async def fake_callback(db: Any, settings: Any, **kwargs: Any) -> tuple[str, Any]:
        assert kwargs["verifier"] == "ver" and kwargs["nonce"] == "non"
        return "signed-sid", SimpleNamespace(sub="s")

    monkeypatch.setattr(service, "oidc_callback", fake_callback)
    client.cookies.set("ev_oidc_tx", _tx_cookie("pwa"))
    response = client.get("/api/auth/callback?code=c&state=st")
    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:8081/events"
    assert response.cookies["ev_session"] == "signed-sid"
    assert state["db"].committed == 1
    set_cookie = response.headers.get_list("set-cookie")
    assert any(
        "ev_session" in c and "HttpOnly" in c and "Max-Age=15552000" in c for c in set_cookie
    )
    assert any("ev_oidc_tx" in c and "Max-Age=0" in c for c in set_cookie)


@pytest.mark.parametrize(
    ("error", "status"), [(OidcError("bad"), 400), (OidcUnavailableError("down"), 503)]
)
def test_callback_maps_idp_errors(
    app_client: tuple[TestClient, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: int,
) -> None:
    async def fail(*args: Any, **kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(service, "oidc_callback", fail)
    client = app_client[0]
    client.cookies.set("ev_oidc_tx", _tx_cookie())
    assert client.get("/api/auth/callback?code=c&state=st").status_code == status


@pytest.mark.parametrize("cookie", [None, "garbage"])
def test_callback_rejects_a_missing_or_broken_transaction(
    app_client: tuple[TestClient, dict[str, Any]], cookie: str | None
) -> None:
    client = app_client[0]
    if cookie:
        client.cookies.set("ev_oidc_tx", cookie)
    assert client.get("/api/auth/callback?code=c&state=st").status_code == 400


def test_callback_rejects_a_state_mismatch(app_client: tuple[TestClient, dict[str, Any]]) -> None:
    client = app_client[0]
    client.cookies.set("ev_oidc_tx", _tx_cookie())
    assert client.get("/api/auth/callback?code=c&state=other").status_code == 400


def test_login_and_callback_are_404_without_oidc(
    app_client: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = app_client
    state["settings"] = make_settings()
    assert client.get("/api/auth/login").status_code == 404
    assert client.get("/api/auth/callback?code=c&state=s").status_code == 404


def test_logout_returns_the_idp_url_and_clears_the_cookie(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = app_client
    row = SimpleNamespace(id_token="idt", sid="sid-1")
    state["db"] = fake_session(result(row))

    async def fake_end(settings: Any, *, id_token: str | None) -> str:
        return f"http://idp/logout?hint={id_token}"

    monkeypatch.setattr(oidc, "end_session_url", fake_end)
    client.cookies.set("ev_session", sessions.sign_principal_sid(SECRET, "sid-1"))
    client.cookies.set("XSRF-TOKEN", "t")
    response = client.post("/api/auth/logout", headers={"X-XSRF-TOKEN": "t"})
    assert response.status_code == 200
    assert response.json() == {"logoutUrl": "http://idp/logout?hint=idt"}
    assert state["db"].deleted == [row]
    assert any(
        "ev_session" in c and "Max-Age=0" in c for c in response.headers.get_list("set-cookie")
    )


def test_logout_survives_a_dead_idp_and_a_missing_session(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = app_client
    assert client.post("/api/auth/logout").json() == {"logoutUrl": None}

    async def boom(*args: Any, **kwargs: Any) -> str:
        raise OidcError("down")

    monkeypatch.setattr(oidc, "end_session_url", boom)
    state["db"] = fake_session(result(SimpleNamespace(id_token=None, sid="sid-1")))
    client.cookies.set("ev_session", sessions.sign_principal_sid(SECRET, "sid-1"))
    client.cookies.set("XSRF-TOKEN", "t")
    response = client.post("/api/auth/logout", headers={"X-XSRF-TOKEN": "t"})
    assert response.json() == {"logoutUrl": None}


def test_me_lists_roles_permissions_and_organizations(
    app_client: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = app_client
    principal = make_principal("events-fsi-organizer", "events-editor")
    principal.email, principal.display_name = "a@b.de", "Ada"
    client.app.dependency_overrides[get_current_principal] = lambda: principal  # type: ignore[attr-defined]
    expires = datetime.now(UTC) + timedelta(days=3)
    org = SimpleNamespace(id=FSI_ID, slug="fsi", name="Fachschaft Informatik", short="FSI")
    state["db"] = fake_session(
        result(SimpleNamespace(sid="sid-1", expires_at=expires)), result(org)
    )
    client.cookies.set("ev_session", sessions.sign_principal_sid(SECRET, "sid-1"))
    response = client.get("/api/auth/me")
    body = response.json()
    assert body["sub"] == "sub-1" and body["displayName"] == "Ada"
    assert body["roles"] == ["editor", "member"]
    assert body["organizations"] == [
        {
            "slug": "fsi",
            "role": "organizer",
            "organizationId": str(FSI_ID),
            "name": "Fachschaft Informatik",
            "short": "FSI",
        }
    ]
    assert "event.publish" in body["permissions"] and "event.restore" in body["permissions"]
    assert body["groups"] == ["events-editor", "events-fsi-organizer"]
    assert any("ev_session" in c for c in response.headers.get_list("set-cookie"))


def test_callback_without_return_to_lands_on_the_base_url(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = app_client

    async def fake_callback(db: Any, settings: Any, **kwargs: Any) -> tuple[str, Any]:
        return "signed-sid", SimpleNamespace(sub="s")

    monkeypatch.setattr(service, "oidc_callback", fake_callback)
    client.cookies.set("ev_oidc_tx", _tx_cookie(return_to=None))
    response = client.get("/api/auth/callback?code=c&state=st")
    assert response.headers["location"] == "http://localhost:8081"


def test_logout_without_oidc_or_without_a_session_row_gives_no_idp_url(
    app_client: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = app_client
    client.cookies.set("ev_session", sessions.sign_principal_sid(SECRET, "sid-1"))
    client.cookies.set("XSRF-TOKEN", "t")
    state["db"] = fake_session(result())
    gone = client.post("/api/auth/logout", headers={"X-XSRF-TOKEN": "t"})
    assert gone.json() == {"logoutUrl": None}
    state["settings"] = make_settings()
    state["db"] = fake_session(result(SimpleNamespace(id_token="idt", sid="sid-1")))
    local = client.post("/api/auth/logout", headers={"X-XSRF-TOKEN": "t"})
    assert local.json() == {"logoutUrl": None}


def test_me_does_not_renew_the_cookie_of_an_unknown_session(
    app_client: tuple[TestClient, dict[str, Any]],
) -> None:
    client, state = app_client
    principal = make_principal("events-editor")
    client.app.dependency_overrides[get_current_principal] = lambda: principal  # type: ignore[attr-defined]
    state["db"] = fake_session(result())
    client.cookies.set("ev_session", sessions.sign_principal_sid(SECRET, "sid-1"))
    response = client.get("/api/auth/me")
    assert response.status_code == 200 and response.json()["organizations"] == []
    assert not any("ev_session" in c for c in response.headers.get_list("set-cookie"))


def test_a_signed_transaction_cookie_without_the_keys_is_refused() -> None:
    forged = sessions._serializer(SECRET, sessions._OIDC_TX_SALT).dumps({"x": 1})
    assert sessions.load_oidc_tx(SECRET, forged, 600) is None


def _revoke(
    client: TestClient, state: dict[str, Any], *results: Any, cookie: str | None = None
) -> Any:
    principal = make_principal("events-editor")
    client.app.dependency_overrides[get_current_principal] = lambda: principal  # type: ignore[attr-defined]
    state["db"] = fake_session(*results)
    if cookie:
        client.cookies.set("ev_session", cookie)
    client.cookies.set("XSRF-TOKEN", "t")
    return client.post("/api/auth/sessions/revoke", headers={"X-XSRF-TOKEN": "t"})


def test_revoke_is_a_noop_for_a_person_without_a_row(
    app_client: tuple[TestClient, dict[str, Any]],
) -> None:
    response = _revoke(*app_client, result())
    assert response.status_code == 200 and response.json() == {"revoked": 0}


def test_revoke_keeps_the_session_of_the_cookie(
    app_client: tuple[TestClient, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, state = app_client
    kept: list[Any] = []
    audits: list[Any] = []

    async def end_other(db: Any, principal_id: Any, keep_sid: Any) -> int:
        kept.append(keep_sid)
        return 3

    async def audit(db: Any, **kwargs: Any) -> None:
        audits.append(kwargs)

    from app.modules.auth import router as auth_router

    monkeypatch.setattr(sessions, "end_other_principal_sessions", end_other)
    monkeypatch.setattr(auth_router, "audit_record", audit)
    person = SimpleNamespace(id="pid", sub="sub-1")
    expires = datetime.now(UTC) + timedelta(days=1)
    session_row = SimpleNamespace(sid="sid-1", expires_at=expires)
    cookie = sessions.sign_principal_sid(SECRET, "sid-1")
    with_cookie = _revoke(client, state, result(person), result(session_row), cookie=cookie)
    assert with_cookie.json() == {"revoked": 3} and kept == ["sid-1"]
    assert audits[0]["data"] == {"scope": "own", "count": 3}
    client.cookies.clear()
    without = _revoke(client, state, result(person))
    assert without.json() == {"revoked": 3} and kept[-1] is None
