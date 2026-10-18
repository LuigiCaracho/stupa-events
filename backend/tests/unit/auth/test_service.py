"""OIDC callback orchestration with fakes: upsert, deactivation, bootstrap, session, audit."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.auth import oidc, service
from app.modules.auth.oidc import OidcClaims
from app.shared.errors import ForbiddenError
from tests._support.auth_fakes import fake_session, result
from tests._support.factories import make_settings

CLAIMS = OidcClaims(
    sub="s-1", email="a@b.de", name="Ada", groups=["events-editor"], email_verified=True
)


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []

    async def exchange(settings: Any, **kwargs: Any) -> dict[str, str]:
        return {"id_token": "idt", "refresh_token": "rt"}

    async def verify(settings: Any, **kwargs: Any) -> OidcClaims:
        return CLAIMS

    async def audit(db: Any, **kwargs: Any) -> None:
        audits.append(kwargs)

    monkeypatch.setattr(oidc, "exchange_code", exchange)
    monkeypatch.setattr(oidc, "verify_id_token", verify)
    monkeypatch.setattr(service, "audit_record", audit)
    return audits


async def test_upsert_creates_and_updates() -> None:
    db = fake_session(result())
    row = await service.upsert_principal(db, CLAIMS)
    assert (row.sub, row.email, row.display_name) == ("s-1", "a@b.de", "Ada")
    assert row.oidc_groups == ["events-editor"] and row.last_login is not None
    existing = SimpleNamespace(sub="s-1")
    again = await service.upsert_principal(fake_session(result(existing)), CLAIMS)
    assert again is existing and existing.oidc_groups == ["events-editor"]


async def test_upsert_runs_the_membership_sync_for_the_stored_row(sync_calls: list[Any]) -> None:
    row = await service.upsert_principal(fake_session(result()), CLAIMS)
    assert sync_calls == [row]


async def test_callback_opens_a_session_and_audits_the_login(idp: list[dict[str, Any]]) -> None:
    db = fake_session(result())
    cookie, row = await service.oidc_callback(
        db,
        make_settings(bootstrap_admin_subjects="s-1"),
        code="c",
        verifier="v",
        nonce="n",
        client="pwa",
    )
    assert cookie and row.bootstrap_admin
    session_row = next(a for a in db.added if hasattr(a, "refresh_token"))
    assert session_row.refresh_token == "rt" and session_row.client == "pwa"
    assert idp == [
        {
            "actor": "s-1",
            "action": "login",
            "target_type": "principal",
            "target_id": str(row.id),
            "data": {"method": "oidc"},
        }
    ]


async def test_deactivated_account_gets_no_session(idp: list[dict[str, Any]]) -> None:
    inactive = SimpleNamespace(sub="s-1", active=False)
    db = fake_session(result(inactive))
    with pytest.raises(ForbiddenError):
        await service.oidc_callback(db, make_settings(), code="c", verifier="v", nonce="n")
    assert idp == []
    assert not any(hasattr(a, "refresh_token") for a in db.added)
