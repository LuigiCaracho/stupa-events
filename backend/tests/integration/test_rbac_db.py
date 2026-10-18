"""RBAC resolution and `/auth/me` against a real database (the tables of `0002`/`0003`)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import create_app
from app.modules.auth import rbac, sessions
from app.modules.auth.models import Principal
from app.settings import get_settings
from tests._support.factories import make_settings

pytestmark = pytest.mark.integration

SECRET = "test-session-secret"


@pytest_asyncio.fixture
async def org_tables(engine: Engine, session: AsyncSession) -> AsyncIterator[None]:
    """Make `fsi` untrusted and `makers` trusted and start from an empty mapping table."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM group_mapping"))
        updated = conn.execute(
            text(
                "UPDATE organization SET trusted = (slug = 'makers') "
                "WHERE slug IN ('fsi', 'makers')"
            )
        ).rowcount
        assert updated == 2
    yield
    await session.rollback()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM group_mapping"))


async def _map(session: AsyncSession, group: str, role: str, slug: str | None = None) -> None:
    await session.execute(
        text(
            "INSERT INTO group_mapping (oidc_group, role, organization_id) "
            "VALUES (:g, :r, (SELECT id FROM organization WHERE slug = :s))"
        ),
        {"g": group, "r": role, "s": slug},
    )
    await session.commit()


async def _principal(session: AsyncSession, groups: list[str], **fields: object) -> Principal:
    row = Principal(sub="s-1", email="a@b.de", display_name="Ada", oidc_groups=groups, **fields)
    session.add(row)
    await session.commit()
    return row


async def test_mappings_and_trust_resolve_against_the_real_tables(
    session: AsyncSession, org_tables: None
) -> None:
    await _map(session, "events-fsi-approver", "approver", "fsi")
    await _map(session, "events-makers-approver", "approver", "makers")
    await _map(session, "events-editor", "editor")
    row = await _principal(
        session, ["events-fsi-approver", "events-makers-approver", "events-editor"]
    )
    principal = await rbac.resolve_principal(session, row, make_settings())
    assert principal.org_roles == {
        "fsi": frozenset({"organizer"}),
        "makers": frozenset({"approver"}),
    }
    assert principal.has("event.approve") is True
    assert principal.roles == ["editor", "member"]
    assert set(principal.org_ids) == {"fsi", "makers"}


async def test_a_group_without_a_mapping_grants_nothing(
    session: AsyncSession, org_tables: None
) -> None:
    row = await _principal(session, ["events-fsi-organizer", "events-admin"])
    principal = await rbac.resolve_principal(session, row, make_settings())
    assert principal.roles == ["member"] and principal.org_roles == {}


async def test_group_mapping_row_grants_an_org_role(
    session: AsyncSession, org_tables: None
) -> None:
    await _map(session, "Fachschaft-Informatik", "organizer", "fsi")
    row = await _principal(session, ["Fachschaft-Informatik"])
    principal = await rbac.resolve_principal(session, row, make_settings())
    assert principal.org_roles == {"fsi": frozenset({"organizer"})}


@pytest_asyncio.fixture
async def api(migrated: tuple[str, str], org_tables: None) -> AsyncIterator[httpx.AsyncClient]:
    settings = make_settings(database_url=migrated[1], cookie_secure=False)
    engine = create_async_engine(migrated[1])
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _db() -> AsyncIterator[AsyncSession]:
        async with maker() as db:
            yield db

    app = create_app(settings)
    app.dependency_overrides[get_session] = _db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield client
    await engine.dispose()


async def test_me_with_a_real_session_cookie(api: httpx.AsyncClient, session: AsyncSession) -> None:
    await _map(session, "events-fsi-organizer", "organizer", "fsi")
    row = await _principal(session, ["events-fsi-organizer", "events-system:events-admin"])
    cookie = await sessions.create_principal_session(
        session,
        secret=SECRET,
        principal_id=row.id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        refresh_token=None,
        id_token=None,
        now=datetime.now(UTC),
    )
    await session.commit()
    anonymous = await api.get("/api/auth/me")
    assert anonymous.status_code == 401
    response = await api.get("/api/auth/me", cookies={"ev_session": cookie})
    assert response.status_code == 200
    body = response.json()
    assert [
        (o["slug"], o["role"], o["name"], o["short"], o["trusted"]) for o in body["organizations"]
    ] == [("fsi", "organizer", "Fachschaft Informatik", "FSI", False)]
    assert body["roles"] == ["member"]
    assert body["groups"] == ["events-fsi-organizer"]
    forged = await api.get("/api/auth/me", cookies={"ev_session": "forged"})
    assert forged.status_code == 401
