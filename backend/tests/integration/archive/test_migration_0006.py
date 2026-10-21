"""Migration 0006 on a database with M4 data: location data step, text cleanup, new objects."""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration
STATES = ("idea", "planning", "in_review", "approved", "live", "followup", "archived", "withdrawn")
EXCEPTION = (
    '{"granted_by": "t", "reason": "Testdaten ohne Motiv", "at": "2026-01-01T00:00:00+00:00"}'
)


def test_upgrade_from_0005_keeps_rows_valid_and_confirms_public_free_text(
    migrated: tuple[str, str],
) -> None:
    sync_url, async_url = migrated
    name = f"m5_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    base = sync_url.rsplit("/", 1)[0]
    old_sync, old_async = f"{base}/{name}", async_url.rsplit("/", 1)[0] + f"/{name}"
    try:
        config = make_alembic_config(old_async)
        command.upgrade(config, "0005_dossier_knowledge")
        engine = create_engine(old_sync)
        with engine.begin() as conn:
            org = conn.execute(text("SELECT id FROM organization WHERE slug = 'fsi'")).scalar_one()
            conn.execute(
                text("UPDATE organization SET short = 'F' || chr(10) || 'S' WHERE slug = 'fsi'")
            )
            conn.execute(
                text(
                    "INSERT INTO venue (slug, name, city) VALUES ('v1', 'Saal', 'Reut' || chr(13) || 'lingen')"
                )
            )
            for state in STATES:
                conn.execute(
                    text(
                        "INSERT INTO event (title, starts_at, ends_at, organization_id, created_by, "
                        "state, venue_text, image_exception, slug) VALUES (:t, now(), "
                        "now() + interval '2 hours', :o, 's', :s, 'Kinosaal 9-133', "
                        "CAST(:x AS jsonb), :slug)"
                    ),
                    {"t": f"E {state}", "o": org, "s": state, "x": EXCEPTION, "slug": f"s-{state}"},
                )
            event = conn.execute(text("SELECT id FROM event WHERE state = 'live'")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO document (event_id, kind, title, body_md) "
                    "VALUES (:e, 'howto', 'A', 'x')"
                ),
                {"e": event},
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT state, location_precision, location_confirmed_by FROM event ORDER BY title"
                )
            ).all()
            cleaned = conn.execute(
                text("SELECT short FROM organization WHERE slug = 'fsi'")
            ).scalar_one()
            city = conn.execute(text("SELECT city FROM venue WHERE slug = 'v1'")).scalar_one()
            formats = conn.execute(text("SELECT count(*) FROM format")).scalar_one()
            view = conn.execute(
                text("SELECT count(*), count(venue_text) FROM public_event_v")
            ).one()
            kinds = conn.execute(
                text("SELECT count(*) FROM document WHERE event_id IS NOT NULL")
            ).scalar_one()
        by_state = {state: (precision, by) for state, precision, by in rows}
        for state in ("live", "followup", "archived"):
            assert by_state[state] == ("building", "system:migration-0006"), state
        for state in ("idea", "planning", "in_review", "approved", "withdrawn"):
            assert by_state[state] == ("hidden", None), state
        assert cleaned == "F S" and city == "Reut lingen" and formats == 7 and kinds == 1
        assert tuple(view) == (3, 3)
        with pytest.raises(DBAPIError, match="ck_document_owner"), engine.begin() as conn:
            conn.execute(
                text("INSERT INTO document (kind, title, body_md) VALUES ('howto', 'x', 'y')")
            )
        with pytest.raises(DBAPIError, match="ck_organization_name_clean"), engine.begin() as conn:
            conn.execute(text("UPDATE organization SET name = 'a' || chr(10) || 'b'"))
        command.downgrade(config, "0005_dossier_knowledge")
        command.upgrade(config, "head")
        engine.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()
