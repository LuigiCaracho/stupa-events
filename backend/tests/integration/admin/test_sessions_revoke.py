"""Session revoke with real cookies: own (the running session stays) and by the admin."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import create_app
from app.modules.auth import sessions
from app.modules.auth.models import Principal
from app.settings import get_settings
from tests._support.factories import make_settings

pytestmark = pytest.mark.integration
CSRF = {"XSRF-TOKEN": "t"}


@dataclass
class World:
    client: httpx.AsyncClient
    maker: async_sessionmaker[AsyncSession]
    admin_id: object
    user_id: object
    admin_cookie: str
    user_cookies: list[str]

    async def call(self, cookie: str, method: str, url: str) -> httpx.Response:
        return await self.client.request(
            method, url, cookies={"ev_session": cookie, **CSRF}, headers={"X-XSRF-TOKEN": "t"}
        )


async def _login(db: AsyncSession, principal: Principal) -> str:
    now = datetime.now(UTC)
    return await sessions.create_principal_session(
        db,
        secret="test-session-secret",
        principal_id=principal.id,
        expires_at=now + timedelta(days=1),
        refresh_token=None,
        id_token=None,
        now=now,
    )


@pytest_asyncio.fixture
async def world(migrated: tuple[str, str], engine: Engine) -> AsyncIterator[World]:
    settings = make_settings(database_url=migrated[1], cookie_secure=False)
    async_engine = create_async_engine(migrated[1])
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM group_mapping"))
        conn.execute(
            text("INSERT INTO group_mapping (oidc_group, role) VALUES ('g-admin', 'admin')")
        )
    async with maker() as db:
        admin = Principal(sub="admin-1", email="admin@example.org", oidc_groups=["g-admin"])
        user = Principal(sub="user-1", email="user@example.org", oidc_groups=[])
        db.add_all([admin, user])
        await db.flush()
        admin_cookie = await _login(db, admin)
        user_cookies = [await _login(db, user) for _ in range(3)]
        await db.commit()

    async def _db() -> AsyncIterator[AsyncSession]:
        async with maker() as db:
            yield db

    app = create_app(settings)
    app.dependency_overrides[get_session] = _db
    app.dependency_overrides[get_settings] = lambda: settings
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield World(client, maker, admin.id, user.id, admin_cookie, user_cookies)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM group_mapping"))
    await async_engine.dispose()


async def audit_rows(world: World) -> list[tuple[str, dict]]:
    async with world.maker() as db:
        rows = await db.execute(
            text("SELECT target_id, data FROM audit_entry WHERE action = 'session_revoke'")
        )
        return [(r.target_id, r.data) for r in rows]


async def test_own_revoke_keeps_the_running_session_and_ends_the_others(world: World) -> None:
    keep, *others = world.user_cookies
    response = await world.call(keep, "POST", "/api/auth/sessions/revoke")
    assert response.status_code == 200 and response.json() == {"revoked": 2}
    assert (await world.call(keep, "GET", "/api/auth/me")).status_code == 200
    for cookie in others:
        assert (await world.call(cookie, "GET", "/api/auth/me")).status_code == 401
    again = await world.call(keep, "POST", "/api/auth/sessions/revoke")
    assert again.json() == {"revoked": 0}
    assert (await audit_rows(world))[0] == (str(world.user_id), {"scope": "own", "count": 2})


async def test_admin_revoke_ends_every_session_of_the_person(world: World) -> None:
    url = f"/api/admin/principals/{world.user_id}/sessions/revoke"
    response = await world.call(world.admin_cookie, "POST", url)
    assert response.status_code == 200 and response.json() == {"revoked": 3}
    for cookie in world.user_cookies:
        assert (await world.call(cookie, "GET", "/api/auth/me")).status_code == 401
    assert (await world.call(world.admin_cookie, "GET", "/api/auth/me")).status_code == 200
    rows = await audit_rows(world)
    assert rows == [(str(world.user_id), {"scope": "admin", "count": 3})]
    assert "@" not in str(rows)


async def test_admin_revoke_of_an_unknown_person_is_404(world: World) -> None:
    url = "/api/admin/principals/00000000-0000-0000-0000-000000000000/sessions/revoke"
    assert (await world.call(world.admin_cookie, "POST", url)).status_code == 404


async def test_a_normal_user_cannot_end_the_sessions_of_others(world: World) -> None:
    url = f"/api/admin/principals/{world.admin_id}/sessions/revoke"
    assert (await world.call(world.user_cookies[0], "POST", url)).status_code == 403
    assert (await world.call(world.admin_cookie, "GET", "/api/auth/me")).status_code == 200


async def test_the_principal_list_shows_open_sessions_and_filters(world: World) -> None:
    listing = (await world.call(world.admin_cookie, "GET", "/api/admin/principals")).json()
    by_sub = {p["sub"]: p for p in listing["items"]}
    assert by_sub["user-1"]["sessionCount"] == 3 and by_sub["admin-1"]["sessionCount"] == 1
    assert listing["total"] == 2 and by_sub["admin-1"]["groups"] == ["g-admin"]
    one = (
        await world.call(world.admin_cookie, "GET", "/api/admin/principals?group=g-admin")
    ).json()
    assert [p["sub"] for p in one["items"]] == ["admin-1"]
    found = (await world.call(world.admin_cookie, "GET", "/api/admin/principals?q=USER")).json()
    assert [p["sub"] for p in found["items"]] == ["user-1"]
    paged = (
        await world.call(world.admin_cookie, "GET", "/api/admin/principals?limit=1&offset=1")
    ).json()
    assert len(paged["items"]) == 1 and paged["total"] == 2
    wildcard = (await world.call(world.admin_cookie, "GET", "/api/admin/principals?q=%25")).json()
    assert wildcard["items"] == []
