"""Migration 0005 on a database with M3 data: kinds, "never shared", media refs, seeds."""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration

IMAGE = "3fa9c1d2-e4b5-4a67-8c90-123456789abc"
OLD_IMAGE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
UNUSED = "11111111-2222-4333-8444-555555555555"


def test_upgrade_from_0004_keeps_rows_valid_and_backfills_media(migrated: tuple[str, str]) -> None:
    sync_url, async_url = migrated
    name = f"m4_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    base = sync_url.rsplit("/", 1)[0]
    old_sync, old_async = f"{base}/{name}", async_url.rsplit("/", 1)[0] + f"/{name}"
    try:
        command.upgrade(make_alembic_config(old_async), "0004_pipeline_full")
        engine = create_engine(old_sync)
        with engine.begin() as conn:
            org = conn.execute(text("SELECT id FROM organization LIMIT 1")).scalar_one()
            event = conn.execute(
                text(
                    "INSERT INTO event (title, starts_at, ends_at, organization_id, created_by, "
                    "description_md) VALUES ('T', now(), now() + interval '2 hours', :o, 's', "
                    "'![x](/api/media/images/" + IMAGE + ")') RETURNING id"
                ),
                {"o": org},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO event_revision (event_id, rev, field_class, snapshot) VALUES "
                    "(:e, 1, 'text', CAST(:s AS jsonb))"
                ),
                {
                    "e": event,
                    "s": '{"description_md": "alt ![y](/api/media/images/' + OLD_IMAGE + ')"}',
                },
            )
            for image in (IMAGE, OLD_IMAGE, UNUSED):
                conn.execute(
                    text(
                        "INSERT INTO markdown_image (id, storage_key, mime, size, width, height) "
                        "VALUES (:i, 'k', 'image/png', 1, 1, 1)"
                    ),
                    {"i": image},
                )
            for kind, visibility, mime in (
                ("businessplan", "shared", "application/pdf"),
                ("poster_print", "org", "application/pdf"),
                ("mail_attachment", "team", "application/pdf"),
                ("quote", "shared", "application/pdf"),
                ("poster", "org", "image/png"),
            ):
                conn.execute(
                    text(
                        "INSERT INTO attachment (event_id, kind, storage_key, display_name, "
                        "storage_name, mime, size_bytes, sha256, visibility) VALUES "
                        "(:e, :k, 'k', 'n', 'n', :m, 10, 'x', :v)"
                    ),
                    {"e": event, "k": kind, "m": mime, "v": visibility},
                )
        command.upgrade(make_alembic_config(old_async), "head")
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT kind, visibility FROM attachment ORDER BY created_at, kind")
            ).all()
            refs = conn.execute(
                text("SELECT image_id::text, owner_type FROM media_ref ORDER BY 1")
            ).all()
            templates = (
                conn.execute(text("SELECT slug FROM checklist_template ORDER BY 1")).scalars().all()
            )
        assert sorted(tuple(r) for r in rows) == sorted(
            [
                ("business_plan", "org"),
                ("other", "org"),
                ("other", "team"),
                ("quote", "org"),
                ("poster", "org"),
            ]
        )
        assert [tuple(r) for r in refs] == [(OLD_IMAGE, "event"), (IMAGE, "event")] or sorted(
            tuple(r) for r in refs
        ) == sorted([(OLD_IMAGE, "event"), (IMAGE, "event")])
        assert templates == ["generic", "meeting", "party", "trip"]
        engine.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def test_a_fresh_database_has_the_same_objects(engine) -> None:  # noqa: ANN001
    with engine.connect() as conn:
        tables = set(
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            ).scalars()
        )
        constraints = set(
            conn.execute(
                text("SELECT conname FROM pg_constraint WHERE conrelid = 'attachment'::regclass")
            ).scalars()
        )
        heads = conn.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    assert heads == ["0008_public_site"]
    assert {
        "document",
        "document_revision",
        "comment",
        "checklist_template",
        "checklist_template_item",
        "checklist_item",
        "quote",
        "notification",
        "notification_pref",
        "media_ref",
    } <= tables
    assert {
        "ck_attachment_kind",
        "ck_attachment_size",
        "ck_attachment_restricted_not_shared",
    } <= constraints
