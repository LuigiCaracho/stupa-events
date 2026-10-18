"""Revalidation and the group cache: an empty `groups` claim withdraws, a missing one keeps (D2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.auth import oidc, session_renewal
from app.modules.auth.models import AuthSession
from app.modules.auth.session_renewal import renew_principal_session
from app.settings import load_settings
from tests._support.auth_fakes import fake_session, result

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def _settings() -> Any:
    return load_settings(
        database_url="postgresql+asyncpg://x/y",
        session_secret="session-secret-0123",
        oidc_issuer="https://sso.example/",
        oidc_client_id="events",
        oidc_client_secret="client-secret-01234",
        oidc_redirect_url="https://events.example/api/auth/callback",
    )


def _session() -> AuthSession:
    row = AuthSession(
        sid="s",
        principal_id="pid",
        expires_at=NOW + timedelta(days=1),
        refresh_token="rt",
        id_token="old",
        client="web",
    )
    row.revalidated_at = NOW - timedelta(hours=5)
    return row


async def _renew(monkeypatch: pytest.MonkeyPatch, token_claims: dict[str, Any]) -> Any:
    """Run one renewal whose refreshed id token carries `token_claims`; return the person."""
    person = SimpleNamespace(
        sub="u", active=True, email="e@x.de", display_name="N", oidc_groups=["events-fsi-organizer"]
    )
    session = _session()

    async def refresh(_s: Any, *, refresh_token: str) -> dict[str, str]:
        return {"id_token": "new", "refresh_token": "rt2"}

    async def decode(_s: Any, _token: str) -> dict[str, Any]:
        return {"sub": "u", **token_claims}

    monkeypatch.setattr(oidc, "refresh_tokens", refresh)
    monkeypatch.setattr(oidc, "_decode_id_token", decode)
    monkeypatch.setattr(session_renewal, "_idp_retry_after", 0.0)
    db = fake_session(result(session), result(person))
    assert await renew_principal_session(
        db, _settings(), session=session, principal=person, now=NOW
    )
    return person


async def test_an_empty_groups_claim_withdraws_every_group(monkeypatch: pytest.MonkeyPatch) -> None:
    person = await _renew(monkeypatch, {"groups": []})
    assert person.oidc_groups == []


async def test_a_missing_groups_claim_keeps_the_cached_groups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = await _renew(monkeypatch, {})
    assert person.oidc_groups == ["events-fsi-organizer"]


async def test_a_changed_groups_claim_replaces_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    person = await _renew(monkeypatch, {"groups": ["events-fsi-viewer"]})
    assert person.oidc_groups == ["events-fsi-viewer"]
