"""Alembic against a real Postgres: one head, short ids, a green upgrade and its objects."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration


def test_single_head_with_short_revision_ids(alembic_cfg: Config) -> None:
    script = ScriptDirectory.from_config(alembic_cfg)
    assert len(script.get_heads()) == 1
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
