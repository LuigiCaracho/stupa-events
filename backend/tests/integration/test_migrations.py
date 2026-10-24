"""Alembic against a real Postgres: one head, short ids, a green upgrade and its objects."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text

pytestmark = pytest.mark.integration


def test_single_head_with_short_revision_ids(alembic_cfg: Config) -> None:
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script.get_heads() == ["0012_purge_rearmed"]
    assert all(len(rev.revision) <= 32 for rev in script.walk_revisions())
    assert script.get_base() == "0001_baseline"


def test_extensions_and_baseline_tables_exist(engine: Engine) -> None:
    with engine.connect() as conn:
        extensions = set(conn.execute(text("SELECT extname FROM pg_extension")).scalars())
        tables = set(
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).scalars()
        )
    assert {"pgcrypto", "citext", "btree_gist", "pg_trgm", "unaccent"} <= extensions
    assert {
        "principal",
        "auth_session",
        "audit_entry",
        "audit_verification",
        "markdown_image",
    } <= tables


def test_german_unaccented_text_search(engine: Engine) -> None:
    with engine.connect() as conn:
        hit = conn.execute(
            text(
                "SELECT to_tsvector('de_unaccent', 'Fachschaftssitzung im Café') "
                "@@ websearch_to_tsquery('de_unaccent', 'cafe')"
            )
        ).scalar_one()
        folded = conn.execute(text("SELECT immutable_unaccent('Übung Ärger')")).scalar_one()
    assert hit is True
    assert folded == "Ubung Arger"


def test_audit_entry_is_append_only_for_everyone(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO audit_entry (action, hash) VALUES ('login', decode('00', 'hex'))")
        )
    for statement in ("UPDATE audit_entry SET action = 'x'", "DELETE FROM audit_entry"):
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text(statement))
    with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
        conn.execute(text("TRUNCATE audit_entry"))


def test_downgrade_and_upgrade_again(migrated: tuple[str, str]) -> None:
    from tests.integration.conftest import make_alembic_config

    cfg = make_alembic_config(migrated[1])
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def _reference_rows(url: str) -> dict[str, list]:
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            return {
                "category": list(
                    conn.execute(text("SELECT id, slug, parent_id FROM category ORDER BY id"))
                ),
                "organization": list(
                    conn.execute(
                        text("SELECT id, slug, legacy_wp_ids FROM organization ORDER BY id")
                    )
                ),
                "venue": list(
                    conn.execute(
                        text("SELECT id, slug, address, legacy_wp_id FROM venue ORDER BY id")
                    )
                ),
            }
    finally:
        eng.dispose()


def test_an_m1_database_upgrades_to_the_same_reference_rows_as_a_fresh_one(
    pg_urls: tuple[str, str], migrated: tuple[str, str]
) -> None:
    from tests.integration.conftest import make_alembic_config

    sync_url, async_url = pg_urls
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS m1upgrade WITH (FORCE)")
        conn.exec_driver_sql("CREATE DATABASE m1upgrade")
    admin.dispose()
    m1_sync = sync_url.rsplit("/", 1)[0] + "/m1upgrade"
    m1_async = async_url.rsplit("/", 1)[0] + "/m1upgrade"
    cfg = make_alembic_config(m1_async)
    command.upgrade(cfg, "0002_events_core")
    eng = create_engine(m1_sync)
    with eng.begin() as conn:
        old = conn.execute(text("SELECT id FROM category WHERE slug = 'lan-party'")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO event (title, starts_at, ends_at, created_by, organization_id, primary_category_id) "
                "SELECT 'Alt', now(), now(), 'm1', o.id, :c FROM organization o WHERE o.slug = 'fsi'"
            ),
            {"c": old},
        )
    eng.dispose()
    command.upgrade(cfg, "head")
    upgraded, fresh = _reference_rows(m1_sync), _reference_rows(migrated[0])
    assert upgraded == fresh
    eng = create_engine(m1_sync)
    with eng.connect() as conn:
        kept = conn.execute(
            text("SELECT c.slug FROM event e JOIN category c ON c.id = e.primary_category_id")
        ).scalar_one()
    eng.dispose()
    assert kept == "lanparty"
    command.downgrade(cfg, "0002_events_core")
    eng = create_engine(m1_sync)
    with eng.connect() as conn:
        assert (
            conn.execute(text("SELECT slug FROM category WHERE id = :i"), {"i": old}).scalar_one()
            == "lan-party"
        )
        assert conn.execute(
            text("SELECT legacy_wp_ids FROM organization WHERE slug = 'tec'")
        ).scalar_one() == [174]
        assert conn.execute(text("SELECT to_regclass('venue')")).scalar_one() is None
    eng.dispose()
