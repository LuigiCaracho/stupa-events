"""Integration harness of the events API: real Postgres, in-memory storage, fake login.

`api` is an HTTP client on the real app with the real database (migrated testcontainer).
A request names its user in the header `X-Test-User`; the fake login builds the principal
through the real `rbac.resolve_principal`, so trust and group mapping behave as in
production. Storage, scan queue and the Redis pool are fakes; `process_poster` runs the
scan and the derive job of the worker in process.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.deps import DbSession, SettingsDep, get_current_principal
from app.main import create_app
from app.modules.auth import rbac
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.dossier.deps import attachment_storage, public_storage, scan_queue
from app.modules.dossier.derive import derive_poster
from app.modules.files.scanner import ScanVerdict
from app.modules.publicapi.db import get_public_session
from tests._support.factories import make_settings, png_bytes
from tests._support.memory_storage import MemoryStorage
from worker.scan import scan_attachment

USERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "editor": ("sub-editor", ("events-editor",)),
    "organizer-fsi": ("sub-org-fsi", ("events-fsi-organizer",)),
    "submitter-fsi": ("sub-sub-fsi", ("events-fsi-submitter",)),
    "submitter2-fsi": ("sub-sub2-fsi", ("events-fsi-submitter",)),
    "viewer-fsi": ("sub-view-fsi", ("events-fsi-viewer",)),
    "approver-fsi": ("sub-app-fsi", ("events-fsi-approver",)),
    "approver-stupa": ("sub-app-stupa", ("events-stupa-approver",)),
    "organizer-makers": ("sub-org-makers", ("events-makers-organizer",)),
    "nobody": ("sub-nobody", ()),
}
ROLES_SQL = Path(__file__).resolve().parents[4] / "deploy" / "db" / "roles.sql"


class FakeScanQueue:
    """Collects the scan jobs the router would enqueue."""

    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue(self, attachment_id: UUID) -> None:
        self.enqueued.append(attachment_id)


class FakePool:
    """Stands in for the arq pool: SET NX, INCR and enqueue_job."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.counters: dict[str, int] = {}
        self.jobs: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    async def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> object:
        self.jobs.append((name, args, kwargs))
        return object()


class CleanScanner:
    """A scanner that finds nothing (or the configured signature)."""

    def __init__(self, signature: str | None = None) -> None:
        self.signature = signature

    async def scan(self, data: bytes) -> ScanVerdict:
        return ScanVerdict(clean=self.signature is None, signature=self.signature)


def future(days: int = 14, hours: int = 0) -> datetime:
    """Return a start time `days` ahead, rounded to the hour."""
    base = datetime.now(UTC) + timedelta(days=days, hours=hours)
    return base.replace(minute=0, second=0, microsecond=0)


@dataclass
class Api:
    """Typed handle around the client and the fakes of one test."""

    client: AsyncClient
    private: MemoryStorage
    public: MemoryStorage
    queue: FakeScanQueue
    pool: FakePool
    maker: async_sessionmaker[AsyncSession]
    org_ids: dict[str, str] = field(default_factory=dict)
    category_ids: dict[str, str] = field(default_factory=dict)

    async def request(self, user: str | None, method: str, url: str, **kw: Any) -> Response:
        headers = {**kw.pop("headers", {}), **({"X-Test-User": user} if user else {})}
        return await self.client.request(method, url, headers=headers, **kw)

    async def create_event(
        self, user: str = "organizer-fsi", org: str = "fsi", **over: Any
    ) -> dict:
        body = {
            "title": "Movienight: Film A",
            "startsAt": future().isoformat(),
            "endsAt": future(hours=3).isoformat(),
            "organizationId": self.org_ids[org],
            "venueText": "Kinosaal 9-133",
            "primaryCategoryId": self.category_ids["kino"],
            "summary": "Ein Film, ein Saal, gute Laune.",
            **over,
        }
        response = await self.request(user, "POST", "/api/events", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    async def fire(self, user: str, event_id: str, transition: str) -> Response:
        return await self.request(
            user, "POST", f"/api/events/{event_id}/transitions/{transition}", json={}
        )

    async def upload_poster(
        self,
        user: str,
        event_id: str,
        *,
        data: bytes | None = None,
        name: str = "poster.png",
        **form: str,
    ) -> Response:
        fields = {
            "altText": "Ein Filmplakat",
            "credit": "Foto: Ada",
            "rightsBasis": "own_work",
            **form,
        }
        return await self.request(
            user,
            "POST",
            f"/api/events/{event_id}/poster",
            data=fields,
            files={"file": (name, data or png_bytes(), "image/png")},
        )

    async def process_poster(self, attachment_id: str, *, signature: str | None = None) -> str:
        """Run the scan job and, after a clean scan, the derive job."""
        pool = FakePool()
        ctx: dict[str, Any] = {
            "settings": make_settings(),
            "scanner": CleanScanner(signature),
            "object_storage": self.private,
            "public_storage": self.public,
            "files_sessionmaker": self.maker,
            "redis": pool,
        }
        verdict = await scan_attachment(ctx, attachment_id)
        if verdict == "clean":
            assert [job[0] for job in pool.jobs] == ["derive_poster"]
            await derive_poster(ctx, attachment_id)
        return verdict

    async def approved_ready_event(self) -> dict:
        """An event in `in_review` with a clean, derived poster."""
        event = await self.create_event()
        eid = event["id"]
        assert (await self.fire("organizer-fsi", eid, "T01")).status_code == 200
        poster = await self.upload_poster("organizer-fsi", eid)
        assert poster.status_code == 201, poster.text
        assert await self.process_poster(poster.json()["id"]) == "clean"
        assert (await self.fire("organizer-fsi", eid, "T02")).status_code == 200
        return (await self.request("editor", "GET", f"/api/events/{eid}")).json()


@pytest.fixture(scope="session")
def db_roles(migrated: tuple[str, str]) -> tuple[str, str]:
    """Create the least-privilege roles like `deploy/db/roles.sql` does; return both URLs."""
    sync_url = migrated[0]
    eng = create_engine(sync_url)
    with eng.begin() as conn:
        db = conn.execute(text("SELECT current_database()")).scalar_one()
        script = ROLES_SQL.read_text().replace("DATABASE events", f"DATABASE {db}")
        script = re.sub(r"ALTER ROLE events_public SET [^;]+;", "", script)
        conn.exec_driver_sql(script.replace("%", "%%"))
        for role in ("events_app", "events_public"):
            conn.execute(text(f"ALTER ROLE {role} PASSWORD 'pw'"))
        conn.execute(
            text("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO events_app")
        )
        conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO events_app"))
        conn.exec_driver_sql(script.replace("%", "%%"))
    eng.dispose()
    return (
        sync_url.replace("test:test", "events_app:pw"),
        sync_url.replace("test:test", "events_public:pw"),
    )


@pytest.fixture(autouse=True)
def clean_events(engine: Engine) -> Iterator[None]:
    """Empty the event tables (the append-only triggers are off for the superuser)."""

    def wipe() -> None:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL session_replication_role = replica"))
            conn.execute(
                text(
                    "TRUNCATE event, attachment, event_revision, event_status_event, "
                    "group_mapping RESTART IDENTITY CASCADE"
                )
            )

    wipe()
    yield
    wipe()


def _fake_login(maker: async_sessionmaker[AsyncSession]):  # noqa: ANN202
    async def login(request: Request, db: DbSession, settings: SettingsDep):  # noqa: ANN202
        name = request.headers.get("x-test-user")
        if name is None:
            return None
        sub, groups = USERS[name]
        row = PrincipalRow(sub=sub, email=f"{name}@example.org", oidc_groups=list(groups))
        row.active = True
        row.bootstrap_admin = False
        return await rbac.resolve_principal(db, row, settings)

    return login


@pytest_asyncio.fixture
async def api(
    migrated: tuple[str, str], engine: Engine, db_roles: tuple[str, str]
) -> AsyncIterator[Api]:
    """The client on the real app and the migrated database."""
    async_engine = create_async_engine(migrated[1])
    public_engine = create_async_engine(
        db_roles[1].replace("postgresql+psycopg", "postgresql+asyncpg")
    )
    maker = async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
    public_maker = async_sessionmaker(public_engine, expire_on_commit=False, autoflush=False)
    private, public, queue, pool = MemoryStorage(), MemoryStorage(), FakeScanQueue(), FakePool()

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def public_session_override() -> AsyncIterator[AsyncSession]:
        async with public_maker() as session:
            yield session

    app = create_app(make_settings())
    app.state.arq_pool = pool
    overrides = app.dependency_overrides
    overrides[get_session] = session_override
    overrides[get_public_session] = public_session_override
    overrides[get_current_principal] = _fake_login(maker)
    overrides[attachment_storage] = lambda: private
    overrides[public_storage] = lambda: public
    overrides[scan_queue] = lambda: queue
    handle = Api(
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
        private,
        public,
        queue,
        pool,
        maker,
    )
    async with maker() as session:
        rows = await session.execute(text("SELECT slug, id FROM organization"))
        handle.org_ids = {slug: str(oid) for slug, oid in rows}
        rows = await session.execute(text("SELECT slug, id FROM category"))
        handle.category_ids = {slug: str(cid) for slug, cid in rows}
    try:
        yield handle
    finally:
        await handle.client.aclose()
        await async_engine.dispose()
        await public_engine.dispose()
