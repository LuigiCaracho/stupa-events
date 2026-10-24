"""Migration 0009: the subscription tables, the seeded interests and the privacy functions."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text

from app.modules.taxonomy.reference import reference_id
from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration

TABLES = {"interest", "subscriber", "subscription_profile", "outbox", "listmonk_list", "digest_run"}
FUNCTIONS = {
    "privacy_erase_subscriber",
    "privacy_purge_pending",
    "privacy_anonymize_unsubscribed",
    "privacy_purge_profiles",
    "privacy_purge_outbox",
}


@contextmanager
def scratch_database(migrated: tuple[str, str], target: str) -> Iterator[tuple[Engine, object]]:
    sync_url, async_url = migrated
    name = f"b3_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    config = make_alembic_config(async_url.rsplit("/", 1)[0] + f"/{name}")
    command.upgrade(config, target)
    engine = create_engine(sync_url.rsplit("/", 1)[0] + f"/{name}")
    try:
        yield engine, config
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def objects(engine: Engine) -> tuple[set[str], set[str]]:
    with engine.connect() as conn:
        tables = set(
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        )
        functions = set(
            conn.execute(
                text("SELECT proname FROM pg_proc WHERE proname LIKE 'privacy\\_%'")
            ).scalars()
        )
    return tables, functions


def test_upgrade_creates_the_tables_functions_and_interests(migrated: tuple[str, str]) -> None:
    with scratch_database(migrated, "0009_subscriptions") as (engine, _):
        tables, functions = objects(engine)
        assert TABLES <= tables
        assert functions == FUNCTIONS
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT slug, category_ids FROM interest")).all()
        by_slug = dict(rows)
        assert set(by_slug) == {"party", "kultur", "sport", "gaming", "lernen", "sitzung"}
        assert set(by_slug["party"]) == {
            reference_id("category", s) for s in ("party", "campusfest", "festival", "get-together")
        }


def test_downgrade_removes_everything_and_upgrade_again_works(migrated: tuple[str, str]) -> None:
    with scratch_database(migrated, "0009_subscriptions") as (engine, config):
        command.downgrade(config, "0008_public_site")  # type: ignore[arg-type]
        tables, functions = objects(engine)
        assert not TABLES & tables
        assert not functions
        command.upgrade(config, "0009_subscriptions")  # type: ignore[arg-type]
        assert TABLES <= objects(engine)[0]


def test_erase_leaves_a_tombstone_without_personal_data(migrated: tuple[str, str]) -> None:
    with scratch_database(migrated, "0009_subscriptions") as (engine, _), engine.begin() as conn:
        sid = conn.execute(
            text(
                "INSERT INTO subscriber (email_enc, email_hmac, status, consent_text_version, "
                "consent_categories, consent_at, listmonk_subscriber_id, manage_token_hash) "
                "VALUES ('\\x01', 'hmac', 'confirmed', 'v', '{party}', now(), 7, 'm') RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO subscription_profile (subscriber_id, questionnaire_version, "
                "interests, categories, ics_token_hash) VALUES (:s, 1, '[\"party\"]', '{party}', 'h')"
            ),
            {"s": sid},
        )
        conn.execute(
            text(
                "INSERT INTO outbox (op, subscriber_id, idempotency_key) "
                "VALUES ('upsert', :s, 'upsert:x:1')"
            ),
            {"s": sid},
        )
        assert conn.execute(text("SELECT privacy_erase_subscriber(:s)"), {"s": sid}).scalar() == 1
        assert conn.execute(text("SELECT privacy_erase_subscriber(:s)"), {"s": sid}).scalar() == 0
        row = (
            conn.execute(text("SELECT * FROM subscriber WHERE id = :s"), {"s": sid})
            .mappings()
            .one()
        )
        assert row["status"] == "erased"
        for column in (
            "email_enc",
            "email_hmac",
            "manage_token_hash",
            "listmonk_subscriber_id",
        ):
            assert row[column] is None
        assert row["consent_categories"] == []
        assert conn.execute(text("SELECT count(*) FROM subscription_profile")).scalar() == 0
        states = dict(conn.execute(text("SELECT op, state FROM outbox")).all())
        assert states == {"upsert": "done", "delete": "pending"}
        payload = conn.execute(text("SELECT payload FROM outbox WHERE op = 'delete'")).scalar()
        assert payload == {"listmonkSubscriberId": 7, "emailEnc": "AQ=="}
