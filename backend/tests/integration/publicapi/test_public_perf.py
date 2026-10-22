"""Performance of the public site routes on 5000 synthetic events (contract 6.1 item 12).

Marker `perf`, not part of the default or the `integration` run: `uv run pytest -m perf`. The
numbers come from the in-process ASGI app against a throwaway Postgres container, the response
cache off, so every request reaches the view. They belong in the acceptance record.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import create_app
from app.modules.publicapi.db import get_public_session
from app.settings import get_settings
from scripts import b1_load
from tests._support.factories import make_settings
from tests.integration.events.harness import db_roles  # noqa: F401
from tests.integration.publicapi.test_search_corpus import CORPUS

pytestmark = pytest.mark.perf


@pytest.fixture
async def client(migrated: tuple[str, str], db_roles: tuple[str, str]):  # noqa: ANN201, F811
    engine = create_engine(migrated[0])
    slugs = b1_load.seed_events(engine, 5000)
    engine.dispose()
    public = create_async_engine(db_roles[1].replace("postgresql+psycopg", "postgresql+asyncpg"))
    maker = async_sessionmaker(public, expire_on_commit=False, autoflush=False)

    async def session():  # noqa: ANN202
        async with maker() as one:
            yield one

    app = create_app(make_settings())
    app.state.arq_pool = None
    app.dependency_overrides[get_public_session] = session
    settings = make_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, slugs, maker
    await public.dispose()


async def test_p95_stays_under_300_ms_and_the_plan_is_recorded(client) -> None:  # noqa: ANN001
    http, slugs, maker = client
    stats = [
        await b1_load.measure(http, name, route, b1_load.MIN_REQUESTS)
        for name, route in b1_load.routes(slugs).items()
    ]
    print("\n" + b1_load.report(stats))
    for stat in stats:
        assert stat.p95 < b1_load.LIMIT_MS, stat
    async with maker() as one:
        plan = (await one.execute(b1_load.explain_statement("Movienight"))).scalar_one()
    nodes = b1_load.plan_nodes(plan)
    print("search plan:", nodes)
    assert ("Seq Scan", "event") in nodes or any(name.startswith("ix_event") for _, name in nodes)


async def test_the_samples_still_hit_on_the_big_stock(client) -> None:  # noqa: ANN001
    http, _, _ = client
    for case in CORPUS:
        if "status" in case or not case.get("contains"):
            continue
        response = await http.get("/api/public/events", params={"q": case["q"], "limit": 50})
        assert response.status_code == 200 and response.json()["items"], case["q"]
