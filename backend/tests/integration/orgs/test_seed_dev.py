"""`scripts/seed_dev.py` runs twice without duplicates and goes through the services."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.taxonomy.seeding import ensure_reference
from scripts import seed_dev
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration
REALM = Path(__file__).resolve().parents[4] / "deploy" / "keycloak" / "stupa-events-realm.json"


async def test_seed_is_idempotent(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_dev, "get_sessionmaker", lambda: api.maker)
    assert await seed_dev.main() == 11
    async with api.maker() as session:
        mappings_after_first = (
            await session.execute(
                text("SELECT count(*) FROM audit_entry WHERE action = 'role_mapping_change'")
            )
        ).scalar_one()
    assert await seed_dev.main() == 0
    async with api.maker() as session:
        states = (
            await session.execute(text("SELECT title, state, venue_text FROM event ORDER BY title"))
        ).all()
        revisions = (
            await session.execute(text("SELECT count(*) FROM event_revision"))
        ).scalar_one()
        chain = (await session.execute(text("SELECT count(*) FROM audit_entry"))).scalar_one()
    by_title = {t: s for t, s, _ in states}
    assert by_title["Movienight: Beispielfilm"] == "draft"
    assert by_title["Spieleabend: Brettspielklassiker"] == "published"
    assert by_title["Archivtreffen"] == "archived"
    assert sorted(set(by_title.values())) == ["archived", "draft", "published"]
    assert {t: v for t, _, v in states}["Movienight: Beispielfilm"] == "Kinosaal 9-133"
    assert revisions == 31
    assert chain == 36 + mappings_after_first


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


async def test_seed_maps_every_realm_group(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed_dev, "get_sessionmaker", lambda: api.maker)
    async with api.maker() as session:
        await session.execute(text("DELETE FROM group_mapping"))
        await session.commit()
    await seed_dev.main()
    realm = json.loads((REALM).read_text(encoding="utf-8"))
    async with api.maker() as session:
        mapped = set(
            (await session.execute(text("SELECT oidc_group FROM group_mapping"))).scalars()
        )
    assert {g["name"] for g in realm["groups"]} - {"events-users"} <= mapped
