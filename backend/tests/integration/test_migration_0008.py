"""Migration 0008: the views gain `search_tsv`, `description`, `sort` and `active`; the downgrade restores them."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from app.modules.publicapi.allowlist import PUBLIC_CATEGORY_COLUMNS, PUBLIC_VIEW_COLUMNS
from tests.integration.conftest import make_alembic_config
from tests.integration.events.harness import db_roles  # noqa: F401

pytestmark = pytest.mark.integration
MAP_COLUMNS = 4


@contextmanager
def database_at_0007(migrated: tuple[str, str]) -> Iterator[tuple[Engine, object, str]]:
    sync_url, async_url = migrated
    name = f"b1_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    base = sync_url.rsplit("/", 1)[0]
    config = make_alembic_config(async_url.rsplit("/", 1)[0] + f"/{name}")
    command.upgrade(config, "0007_event_dossier")
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
        for state, published in (
            ("draft", False),
            ("published", True),
            ("archived", True),
            ("archived", False),
        ):
            conn.execute(
                text(
                    "INSERT INTO event (title, summary, description_md, starts_at, ends_at, "
                    "organization_id, created_by, state, slug, tzid, published_at) VALUES "
                    "(:t, 'Kurztext', 'Langtext Kinoabend', now(), now() + interval '2 hours', :o, "
                    "'s', :s, :slug, 'Europe/Berlin', CASE WHEN :p THEN now() END)"
                ),
                {
                    "t": f"E {state} {published}",
                    "o": org,
                    "s": state,
                    "slug": f"s-{state}-{published}",
                    "p": published,
                },
            )


def view_columns(engine: Engine, view: str) -> tuple[str, ...]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = :v "
                "ORDER BY ordinal_position"
            ),
            {"v": view},
        )
        return tuple(r[0] for r in rows)


@pytest.mark.usefixtures("db_roles")
def test_upgrade_adds_the_columns_without_changing_the_rows(
    migrated: tuple[str, str],
) -> None:
    with database_at_0007(migrated) as (engine, config, url):
        seed(engine)
        with engine.connect() as conn:
            before = (
                conn.execute(text("SELECT slug FROM public_event_v ORDER BY slug")).scalars().all()
            )
        command.upgrade(config, "0008_public_site")  # type: ignore[arg-type]
        with engine.connect() as conn:
            after = (
                conn.execute(text("SELECT slug FROM public_event_v ORDER BY slug")).scalars().all()
            )
            hits = conn.execute(
                text(
                    "SELECT count(*) FROM public_event_v WHERE search_tsv @@ plainto_tsquery('de_unaccent', 'kinoabend')"
                )
            ).scalar_one()
            description = conn.execute(
                text("SELECT description FROM category WHERE slug = 'kino'")
            ).scalar_one()
        assert before == after == ["s-archived-True", "s-published-True"] and hits == 2
        assert description == "Movienight und Filmabende"
        assert view_columns(engine, "public_event_v") == PUBLIC_VIEW_COLUMNS[:-MAP_COLUMNS]
        assert view_columns(engine, "public_category_v") == PUBLIC_CATEGORY_COLUMNS
        public = create_engine(url.replace("test:test", "events_public:pw"))
        with public.connect() as conn:
            assert (
                conn.execute(text("SELECT count(search_tsv) FROM public_event_v")).scalar_one() == 2
            )
            assert conn.execute(
                text("SELECT count(*) FROM public_category_v WHERE active")
            ).scalar_one()
        with public.connect() as conn, pytest.raises(DBAPIError):
            conn.execute(text("SELECT search_tsv FROM event"))
        public.dispose()


def test_the_description_is_clean_and_short(migrated: tuple[str, str]) -> None:
    with database_at_0007(migrated) as (engine, config, _):
        command.upgrade(config, "0008_public_site")  # type: ignore[arg-type]
        for value in ("x" * 301, "a b", "a\x07b"):
            with engine.begin() as conn, pytest.raises(DBAPIError) as caught:
                conn.execute(
                    text("UPDATE category SET description = :d WHERE slug = 'kino'"), {"d": value}
                )
            assert "ck_category_description_ok" in str(caught.value)


@pytest.mark.usefixtures("db_roles")
def test_downgrade_restores_the_old_views_and_drops_the_column(
    migrated: tuple[str, str],
) -> None:
    with database_at_0007(migrated) as (engine, config, url):
        seed(engine)
        old_event = view_columns(engine, "public_event_v")
        old_category = view_columns(engine, "public_category_v")
        command.upgrade(config, "0008_public_site")  # type: ignore[arg-type]
        command.downgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        assert view_columns(engine, "public_event_v") == old_event
        assert view_columns(engine, "public_category_v") == old_category
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public_event_v")).scalar_one() == 2
            assert not conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = 'category' AND column_name = 'description'"
                )
            ).all()
        public = create_engine(url.replace("test:test", "events_public:pw"))
        with public.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM public_event_v")).scalar_one() == 2
        public.dispose()
        command.upgrade(config, "head")  # type: ignore[arg-type]
