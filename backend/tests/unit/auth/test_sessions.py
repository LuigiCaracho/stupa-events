"""Session helpers: the return-to whitelist, the transaction cookie, sid signing, bootstrap."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.auth import bootstrap, sessions
from app.modules.auth.models import session_days
from tests._support.factories import make_settings


@pytest.mark.parametrize("value", ["/", "/events", "/events/1?tab=a#x", "/e/2026-11-05-x"])
def test_safe_return_to_accepts_app_paths(value: str) -> None:
    assert sessions.safe_return_to(value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "events",
        "//evil.example",
        "https://evil.example",
        "/\\evil",
        "/a b",
        "/api/auth/me",
        "/api",
        "/a/../api/x",
        "/%2e%2e/api",
        "/x%2Fy",
        "/" + "a" * 1100,
    ],
)
def test_safe_return_to_refuses_everything_else(value: str | None) -> None:
    assert sessions.safe_return_to(value) is None


def test_oidc_tx_roundtrip_and_tamper() -> None:
    cookie = sessions.issue_oidc_tx("secret-secret-1234", "st", "ver", "non", "pwa", "/events")
    tx = sessions.load_oidc_tx("secret-secret-1234", cookie, 600)
    assert tx == {
        "state": "st",
        "verifier": "ver",
        "nonce": "non",
        "client": "pwa",
        "return_to": "/events",
    }
    assert sessions.load_oidc_tx("other-secret-12345", cookie, 600) is None
    assert sessions.load_oidc_tx("secret-secret-1234", cookie + "x", 600) is None


def test_oidc_tx_defaults_to_web_and_drops_unsafe_return_to() -> None:
    cookie = sessions.issue_oidc_tx("secret-secret-1234", "s", "v", "n", "tv", "//evil")
    tx = sessions.load_oidc_tx("secret-secret-1234", cookie, 600)
    assert tx is not None
    assert tx["client"] == "web"
    assert "return_to" not in tx


def test_sid_signature_roundtrip() -> None:
    signed = sessions.sign_principal_sid("secret-secret-1234", "sid-1")
    assert sessions.principal_sid("secret-secret-1234", signed, 60) == "sid-1"
    assert sessions.principal_sid("wrong-secret-12345", signed, 60) is None


def test_session_lifetimes() -> None:
    assert session_days("web") == 90
    assert session_days("pwa") == 180
    assert session_days("anything") == 90


class _Db:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.flushed = False

    async def execute(self, statement: Any) -> Any:
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.rows))

    async def flush(self) -> None:
        self.flushed = True


def _principal(**fields: Any) -> Any:
    return SimpleNamespace(sub="sub-1", email="boss@x.de", bootstrap_admin=False, **fields)


async def test_login_bootstrap_matches_sub_or_verified_email_only() -> None:
    by_sub = make_settings(bootstrap_admin_subjects="sub-1")
    by_mail = make_settings(bootstrap_admin_emails="BOSS@x.de")
    row = _principal()
    assert not await bootstrap.ensure_admin_for_principal(
        _Db([]),
        by_mail,
        row,
        email_verified=False,  # type: ignore[arg-type]
    )
    assert not row.bootstrap_admin
    assert await bootstrap.ensure_admin_for_principal(
        _Db([]),
        by_mail,
        row,
        email_verified=True,  # type: ignore[arg-type]
    )
    other = _principal()
    assert await bootstrap.ensure_admin_for_principal(
        _Db([]),
        by_sub,
        other,
        email_verified=False,  # type: ignore[arg-type]
    )
    assert not await bootstrap.ensure_admin_for_principal(
        _Db([]),
        by_sub,
        other,
        email_verified=True,  # type: ignore[arg-type]
    )


async def test_startup_sweep_flags_listed_subjects() -> None:
    rows = [_principal(), _principal()]
    db = _Db(rows)
    assert (
        await bootstrap.ensure_bootstrap_admins(
            db,
            make_settings(bootstrap_admin_subjects="sub-1"),  # type: ignore[arg-type]
        )
        == 2
    )
    assert all(r.bootstrap_admin for r in rows) and db.flushed
    assert await bootstrap.ensure_bootstrap_admins(_Db([]), make_settings()) == 0  # type: ignore[arg-type]
