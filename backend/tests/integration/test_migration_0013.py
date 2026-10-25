"""Migration 0013: map columns on the view, rounded by precision; campus table and view; round trip."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.modules.publicapi.allowlist import PUBLIC_VIEW_COLUMNS
from tests.integration.conftest import make_alembic_config
from tests.integration.events.harness import db_roles  # noqa: F401
from tests.integration.test_migration_0008 import view_columns

pytestmark = pytest.mark.integration
VENUES = {
    "exact": ("exact", 48.482617, 9.187431, False, "9"),
    "building": ("building", 48.482617, 9.187431, False, "9"),
    "hidden": ("hidden", 48.482617, 9.187431, False, "9"),
    "private": ("exact", 48.482617, 9.187431, True, "9"),
    "bare": ("building", None, None, False, None),
}


@contextmanager
def database_at_0012(migrated: tuple[str, str]) -> Iterator[tuple[Engine, object, str]]:
    sync_url, async_url = migrated
    name = f"c1_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    base = sync_url.rsplit("/", 1)[0]
    config = make_alembic_config(async_url.rsplit("/", 1)[0] + f"/{name}")
    command.upgrade(config, "0012_purge_rearmed")
    engine = create_engine(f"{base}/{name}")
    try:
        yield engine, config, f"{base}/{name}"
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def seed(engine: Engine) -> None:
    with engine.begin() as conn:
        org = conn.execute(text("SELECT id FROM organization WHERE slug = 'fsi'")).scalar_one()
        for key, (precision, lat, lon, private, building) in VENUES.items():
            venue = conn.execute(
                text(
                    "INSERT INTO venue (slug, name, public_precision, lat, lon, is_private, building_no) "
                    "VALUES (:s, :s, :p, :lat, :lon, :priv, :b) RETURNING id"
                ),
                {
                    "s": f"v-{key}",
                    "p": precision,
                    "lat": lat,
                    "lon": lon,
                    "priv": private,
                    "b": building,
                },
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO event (title, summary, description_md, starts_at, ends_at, "
                    "organization_id, created_by, state, slug, tzid, published_at, venue_id) VALUES "
                    "(:t, 'k', 'l', now(), now() + interval '2 hours', :o, 's', 'published', :t, "
                    "'Europe/Berlin', now(), :v)"
                ),
                {"t": f"e-{key}", "o": org, "v": venue},
            )


def mapped(engine: Engine) -> dict[str, tuple]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT slug, venue_lat, venue_lon, venue_geo_precision, venue_building_no "
                "FROM public_event_v"
            )
        )
        return {r[0]: tuple(r[1:]) for r in rows}


@pytest.mark.usefixtures("db_roles")
def test_the_view_rounds_by_precision_and_hides_the_rest(migrated: tuple[str, str]) -> None:
    with database_at_0012(migrated) as (engine, config, url):
        seed(engine)
        command.upgrade(config, "head")  # type: ignore[arg-type]
        assert view_columns(engine, "public_event_v") == PUBLIC_VIEW_COLUMNS
        assert mapped(engine) == {
            "e-exact": (48.482617, 9.187431, "exact", "9"),
            "e-building": (48.483, 9.187, "building", "9"),
            "e-hidden": (None, None, None, None),
            "e-private": (None, None, None, None),
            "e-bare": (None, None, None, None),
        }


@pytest.mark.usefixtures("db_roles")
def test_the_campus_is_seeded_and_the_public_reads_only_the_view(
    migrated: tuple[str, str],
) -> None:
    with database_at_0012(migrated) as (engine, config, url):
        command.upgrade(config, "head")  # type: ignore[arg-type]
        with engine.connect() as conn:
            numbers = conn.execute(text("SELECT number FROM campus_building")).scalars().all()
        assert "9" in numbers and len(numbers) >= 7
        public = create_engine(url.replace("test:test", "events_public:pw"))
        with public.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public_campus_building_v")).scalar_one()
        with public.connect() as conn, pytest.raises(DBAPIError):
            conn.execute(text("SELECT * FROM campus_building"))
        public.dispose()


def test_the_checks_refuse_bad_rows(migrated: tuple[str, str]) -> None:
    with database_at_0012(migrated) as (engine, config, _):
        command.upgrade(config, "head")  # type: ignore[arg-type]
        bad = (
            "INSERT INTO campus_building (number, name, geometry) VALUES ('x9', 'n', '{\"type\":\"Polygon\"}')",
            "INSERT INTO campus_building (number, name, geometry) VALUES ('9z', 'n', '{\"type\":\"Point\"}')",
            "INSERT INTO campus_building (number, name, geometry, approx, osm_ref) "
            "VALUES ('99', 'n', '{\"type\":\"Polygon\"}', true, 'way/1')",
            "INSERT INTO geocode_cache (query_hash, query_norm, found, fetched_at) VALUES ('h', 'q', true, now())",
            "INSERT INTO geocode_cache (query_hash, query_norm, found, fetched_at) VALUES ('h', E'a\\nb', false, now())",
        )
        for statement in bad:
            with engine.begin() as conn, pytest.raises(DBAPIError):
                conn.execute(text(statement))


@pytest.mark.usefixtures("db_roles")
def test_downgrade_restores_the_old_view_and_upgrade_again_works(
    migrated: tuple[str, str],
) -> None:
    with database_at_0012(migrated) as (engine, config, url):
        seed(engine)
        command.upgrade(config, "head")  # type: ignore[arg-type]
        command.downgrade(config, "0012_purge_rearmed")  # type: ignore[arg-type]
        assert view_columns(engine, "public_event_v") == PUBLIC_VIEW_COLUMNS[:-4]
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public_event_v")).scalar_one() == 5
            assert not conn.execute(text("SELECT to_regclass('campus_building')")).scalar_one()
        public = create_engine(url.replace("test:test", "events_public:pw"))
        with public.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public_event_v")).scalar_one() == 5
        public.dispose()
        command.upgrade(config, "head")  # type: ignore[arg-type]
        assert mapped(engine)["e-building"] == (48.483, 9.187, "building", "9")
