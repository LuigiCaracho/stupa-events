"""Reference rows after `0003`: categories, organizations, the 44 venues and the M2 changes."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.modules.taxonomy.reference import CATEGORIES, reference_id
from app.modules.taxonomy.reference_m2 import CATEGORY_SLUG_RENAMES
from app.modules.taxonomy.seeding import ensure_reference
from app.modules.taxonomy.venue_reference import VENUES
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def rows(api: Api, sql: str) -> list:
    async with api.maker() as session:
        return list((await session.execute(text(sql))).all())


async def test_categories_follow_the_wordpress_archive(api: Api) -> None:
    cats = {
        r.slug: r
        for r in await rows(
            api, "SELECT slug, id, kind, parent_id, short, color_token FROM category"
        )
    }
    assert len(cats) == 27
    renamed = dict(CATEGORY_SLUG_RENAMES)
    assert set(cats) == {renamed.get(c["slug"], c["slug"]) for c in CATEGORIES}
    for old, new in renamed.items():
        assert old not in cats and cats[new].id == reference_id("category", old)
    children = [c for c in cats.values() if c.parent_id == cats["fachschaft"].id]
    assert {c.slug for c in children} == {
        "fachschaft-informatik-fsi",
        "fachschaft-technik-tec",
        "fachschaft-texoversum-tex",
        "fachschaft-life-sciences-ls",
        "fachschaft-nxt",
        "esb-stuco",
    }
    colors = {c.short: c.color_token for c in children}
    assert colors == {
        "FSI": "petrol",
        "TEC": "red",
        "TEX": "yellow",
        "LS": "orange",
        "NXT": "blue",
        "ESB": "navy",
    }
    assert cats["ekhg"].parent_id is None and cats["ekhg"].kind == "partner"
    assert cats["lanparty"].kind == "format"


async def test_organizations_after_m2(api: Api) -> None:
    orgs = {
        r.slug: r
        for r in await rows(api, "SELECT slug, legacy_wp_ids, category_id FROM organization")
    }
    assert len(orgs) == 13
    assert orgs["tec"].legacy_wp_ids == []
    assert orgs["fsi"].legacy_wp_ids == [1649]
    assert orgs["fsi"].category_id == reference_id("category", "fachschaft-fsi")


async def test_the_44_venues(api: Api) -> None:
    venues = await rows(
        api,
        "SELECT slug, id, name, address, postcode, city, building_no, room_key, legacy_wp_id, "
        "lat, lon, public_precision, is_private, active, geocode_source FROM venue",
    )
    assert len(venues) == 44
    by_slug = {v.slug: v for v in venues}
    assert {v["slug"] for v in VENUES} == set(by_slug)
    assert all(v.lat is None and v.lon is None and v.geocode_source is None for v in venues)
    assert all(v.public_precision == "hidden" and not v.is_private and v.active for v in venues)
    assert len({v.legacy_wp_id for v in venues}) == 44
    for expected in VENUES:
        row = by_slug[expected["slug"]]
        assert (row.id, row.name, row.address, row.room_key) == (
            expected["id"],
            expected["name"],
            expected["address"],
            expected["room_key"],
        )
    assert by_slug["kinosaal-9-133"].postcode == "72762"
    assert sum(v.address is not None for v in venues) == 9


async def test_ensure_reference_restores_a_missing_venue_and_keeps_edits(api: Api) -> None:
    async with api.maker() as session:
        await session.execute(text("DELETE FROM venue WHERE slug = 'hades'"))
        await session.execute(text("UPDATE venue SET notes = 'meine Notiz' WHERE slug = 'davos'"))
        await session.commit()
        await ensure_reference(session)
        await session.commit()
    after = {r.slug: r.notes for r in await rows(api, "SELECT slug, notes FROM venue")}
    assert len(after) == 44 and after["davos"] == "meine Notiz"
    async with api.maker() as session:
        await session.execute(text("UPDATE venue SET notes = NULL WHERE slug = 'davos'"))
        await session.commit()


async def test_the_venue_table_rejects_bad_coordinates_and_control_characters(api: Api) -> None:
    from sqlalchemy.exc import IntegrityError

    for statement in (
        "UPDATE venue SET lat = 10 WHERE slug = 'davos'",
        "UPDATE venue SET lat = 91, lon = 1 WHERE slug = 'davos'",
        "UPDATE venue SET lat = 1, lon = 181 WHERE slug = 'davos'",
        "UPDATE venue SET public_precision = 'x' WHERE slug = 'davos'",
        "UPDATE venue SET geocode_source = 'x' WHERE slug = 'davos'",
        "UPDATE venue SET name = E'a\\x01b' WHERE slug = 'davos'",
    ):
        async with api.maker() as session:
            with pytest.raises(IntegrityError):
                await session.execute(text(statement))
                await session.commit()
