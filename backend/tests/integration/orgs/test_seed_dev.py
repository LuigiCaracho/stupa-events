"""`scripts/seed_dev.py` runs twice without duplicates and goes through the services."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.modules.taxonomy.seeding import ensure_reference
from scripts import seed_dev
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_seed_is_idempotent(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_dev, "get_sessionmaker", lambda: api.maker)
    assert await seed_dev.main() == 3
    assert await seed_dev.main() == 0
    async with api.maker() as session:
        states = (
            await session.execute(text("SELECT title, state, venue_text FROM event ORDER BY title"))
        ).all()
        revisions = (
            await session.execute(text("SELECT count(*) FROM event_revision"))
        ).scalar_one()
        chain = (await session.execute(text("SELECT count(*) FROM audit_entry"))).scalar_one()
    assert {t: s for t, s, _ in states}["Movienight: Beispielfilm"] == "planning"
    assert {t: v for t, _, v in states}["Movienight: Beispielfilm"] == "Kinosaal 9-133"
    assert revisions == 4 and chain == 4


async def test_ensure_reference_adds_missing_rows_only(api: Api) -> None:
    async with api.maker() as session:
        await session.execute(text("DELETE FROM group_mapping"))
        await session.execute(
            text("UPDATE organization SET name = 'Eigener Name' WHERE slug = 'fsi'")
        )
        await session.commit()
        await ensure_reference(session)
        await session.commit()
        name = (
            await session.execute(text("SELECT name FROM organization WHERE slug = 'fsi'"))
        ).scalar_one()
        total = (await session.execute(text("SELECT count(*) FROM organization"))).scalar_one()
        await session.execute(
            text("UPDATE organization SET name = 'Fachschaft Informatik' WHERE slug = 'fsi'")
        )
        await session.commit()
    assert name == "Eigener Name" and total == 13
