"""Principal upsert, session lifecycle and bootstrap against a real database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth import sessions
from app.modules.auth.bootstrap import ensure_bootstrap_admins
from app.modules.auth.models import AuthSession, Principal
from app.modules.auth.oidc import OidcClaims
from app.modules.auth.service import upsert_principal
from tests._support.factories import make_settings

pytestmark = pytest.mark.integration

SECRET = "test-session-secret"


async def test_upsert_is_idempotent_and_refreshes_the_groups(session: AsyncSession) -> None:
    claims = OidcClaims(sub="s-1", email="Ada@Example.de", name="Ada", groups=["a"])
    first = await upsert_principal(session, claims)
    await session.commit()
    again = await upsert_principal(
        session, OidcClaims(sub="s-1", email="ada@example.de", name="Ada L.", groups=["b"])
    )
    await session.commit()
    assert first.id == again.id
    rows = (await session.execute(select(Principal))).scalars().all()
    assert len(rows) == 1 and rows[0].oidc_groups == ["b"] and rows[0].display_name == "Ada L."


async def test_session_roundtrip_expiry_and_end(session: AsyncSession) -> None:
    row = await upsert_principal(session, OidcClaims(sub="s-1", email=None, name=None))
    now = datetime.now(UTC)
    cookie = await sessions.create_principal_session(
        session,
        secret=SECRET,
        principal_id=row.id,
        expires_at=now + timedelta(days=1),
        refresh_token="rt",
        id_token="idt",
        now=now,
    )
    await session.commit()
    loaded = await sessions.load_principal_session(
        session,
        secret=SECRET,
        cookie_value=cookie,
        now=now,
        max_age=sessions.SESSION_COOKIE_MAX_AGE,
    )
    assert loaded is not None and loaded.refresh_token == "rt"
    later = now + timedelta(days=2)
    assert (
        await sessions.load_principal_session(
            session,
            secret=SECRET,
            cookie_value=cookie,
            now=later,
            max_age=sessions.SESSION_COOKIE_MAX_AGE,
        )
        is None
    )
    await sessions.end_principal_sessions(session, row.id)
    await session.commit()
    assert (await session.execute(select(AuthSession))).scalars().all() == []


async def test_deleting_a_principal_cascades_to_sessions(session: AsyncSession) -> None:
    row = await upsert_principal(session, OidcClaims(sub="s-1", email=None, name=None))
    await sessions.create_principal_session(
        session,
        secret=SECRET,
        principal_id=row.id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        refresh_token=None,
        id_token=None,
    )
    await session.commit()
    await session.delete(row)
    await session.commit()
    assert (await session.execute(select(AuthSession))).scalars().all() == []


async def test_startup_sweep_flags_only_listed_subjects(session: AsyncSession) -> None:
    for sub in ("boss", "other"):
        await upsert_principal(session, OidcClaims(sub=sub, email=None, name=None))
    flagged = await ensure_bootstrap_admins(session, make_settings(bootstrap_admin_subjects="boss"))
    await session.commit()
    assert flagged == 1
    by_sub = {
        r.sub: r.bootstrap_admin for r in (await session.execute(select(Principal))).scalars()
    }
    assert by_sub == {"boss": True, "other": False}
