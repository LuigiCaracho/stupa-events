"""Migration 0007 on a database with pipeline data: states, roles, notices and the dropped objects."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration
OLD_STATES = (
    "idea",
    "planning",
    "in_review",
    "approved",
    "live",
    "followup",
    "archived",
    "withdrawn",
)
WANTED = {
    "idea": "draft",
    "planning": "draft",
    "in_review": "draft",
    "approved": "draft",
    "live": "published",
    "followup": "archived",
    "archived": "archived",
    "withdrawn": "draft",
}
POSTER_DERIVATIVES = '{"thumb_400": {}, "card_1200": {}, "og_1200x630": {}}'
REMOVED_KINDS = (
    "review_requested",
    "changes_requested",
    "transition_done",
    "task_assigned",
    "comment_resolved",
    "followup_reminder",
    "auto_archived",
)


@contextmanager
def database_at_0006(migrated: tuple[str, str]) -> Iterator[tuple[Engine, object]]:
    sync_url, async_url = migrated
    name = f"m5b_{uuid.uuid4().hex[:8]}"
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name}"))
    base = sync_url.rsplit("/", 1)[0]
    config = make_alembic_config(async_url.rsplit("/", 1)[0] + f"/{name}")
    command.upgrade(config, "0006_archive_feed")
    engine = create_engine(f"{base}/{name}")
    try:
        yield engine, config
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def seed_events(engine: Engine) -> dict[str, str]:
    with engine.begin() as conn:
        org = conn.execute(text("SELECT id FROM organization WHERE slug = 'fsi'")).scalar_one()
        ids: dict[str, str] = {}
        for state in OLD_STATES:
            ids[state] = str(
                conn.execute(
                    text(
                        "INSERT INTO event (title, starts_at, ends_at, organization_id, "
                        "created_by, state, slug, image_exception, publish_at, tzid) "
                        "VALUES (:t, now() + interval '1 day', now() + interval '2 days', :o, "
                        "'s', :s, :slug, CAST(:x AS jsonb), :p, 'Europe/Berlin') RETURNING id"
                    ),
                    {
                        "t": f"E {state}",
                        "o": org,
                        "s": state,
                        "slug": f"s-{state}",
                        "x": '{"reason": "Testdaten ohne Motiv"}',
                        "p": "2026-01-01T00:00:00+00:00" if state == "approved" else None,
                    },
                ).scalar_one()
            )
        ids["orphan"] = str(
            conn.execute(
                text(
                    "INSERT INTO event (title, starts_at, ends_at, created_by, state) "
                    "VALUES ('Vorschlag', now(), now(), 's', 'idea') RETURNING id"
                )
            ).scalar_one()
        )
        person = conn.execute(
            text("INSERT INTO principal (sub, email) VALUES ('p-1', 'p@x.de') RETURNING id")
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO membership (principal_id, organization_id, role) VALUES (:p, :o, 'organizer')"
            ),
            {"p": person, "o": org},
        )
        conn.execute(
            text(
                "INSERT INTO membership (principal_id, organization_id, role) VALUES (:p, :o, 'approver')"
            ),
            {"p": person, "o": org},
        )
        other = conn.execute(
            text("INSERT INTO principal (sub, email) VALUES ('p-2', 'q@x.de') RETURNING id")
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO membership (principal_id, organization_id, role) VALUES (:p, :o, 'approver')"
            ),
            {"p": other, "o": org},
        )
        conn.execute(
            text(
                "INSERT INTO group_mapping (oidc_group, role, organization_id) VALUES ('g-app', 'approver', :o)"
            ),
            {"o": org},
        )
        for kind in (*REMOVED_KINDS, "comment_added", "checklist_due"):
            conn.execute(
                text(
                    "INSERT INTO notification (recipient_sub, kind, event_id, link) "
                    "VALUES ('p-1', :k, :e, '/dossiers/x')"
                ),
                {"k": kind, "e": ids["live"]},
            )
            conn.execute(
                text("INSERT INTO notification_pref (principal_sub, kind) VALUES ('p-1', :k)"),
                {"k": kind},
            )
    return ids


def test_upgrade_maps_eight_states_onto_three_and_keeps_the_history(
    migrated: tuple[str, str],
) -> None:
    with database_at_0006(migrated) as (engine, config):
        ids = seed_events(engine)
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        with engine.connect() as conn:
            states = dict(conn.execute(text("SELECT title, state FROM event")).all())
            history = conn.execute(
                text(
                    "SELECT event_id::text, from_state, to_state, actor_id, actor_type, "
                    "transition_id FROM event_status_event WHERE transition_id = 'migration-0007'"
                )
            ).all()
            revs = conn.execute(text("SELECT count(*) FROM event_revision")).scalar_one()
        for old, new in WANTED.items():
            assert states[f"E {old}"] == new, old
        assert states["Vorschlag"] == "draft"
        changed = {row[0]: row for row in history}
        assert set(changed) == {ids[s] for s in OLD_STATES if WANTED[s] != s} | {ids["orphan"]}
        for _, from_state, to_state, actor, actor_type, _ in changed.values():
            assert actor == "system:migration-0007" and actor_type == "system"
            assert to_state == WANTED[from_state]
        assert revs == 0
        assert len(history) == 8


def test_roles_notices_and_constraints(migrated: tuple[str, str]) -> None:
    with database_at_0006(migrated) as (engine, config):
        seed_events(engine)
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        with engine.connect() as conn:
            memberships = conn.execute(
                text(
                    "SELECT p.sub, m.role FROM membership m JOIN principal p ON p.id = m.principal_id ORDER BY 1, 2"
                )
            ).all()
            mapping = conn.execute(text("SELECT role FROM group_mapping")).scalars().all()
            kinds = set(conn.execute(text("SELECT kind FROM notification")).scalars())
            prefs = set(conn.execute(text("SELECT kind FROM notification_pref")).scalars())
        assert memberships == [("p-1", "organizer"), ("p-2", "organizer")]
        assert mapping == ["organizer"]
        assert kinds == prefs == {"comment_added", "checklist_due"}
        for statement, match in (
            ("UPDATE event SET state = 'live'", "ck_event_state"),
            ("UPDATE event SET tzid = 'UTC'", "ck_event_tzid"),
            (
                "INSERT INTO membership (principal_id, organization_id, role) SELECT id, (SELECT id FROM organization LIMIT 1), 'approver' FROM principal LIMIT 1",
                "ck_membership_role",
            ),
            (
                "INSERT INTO notification (recipient_sub, kind, link) VALUES ('x', 'review_requested', '/x')",
                "ck_notification_kind",
            ),
            (
                "UPDATE event SET state = 'published', organization_id = NULL WHERE title = 'E live'",
                "ck_event_organization",
            ),
        ):
            with pytest.raises(DBAPIError, match=match), engine.begin() as conn:
                conn.execute(text(statement))
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO event_status_event (event_id, from_state, to_state, transition_id) "
                    "SELECT id, 'live', 'followup', 'T08' FROM event LIMIT 1"
                )
            )


def test_the_pipeline_objects_are_gone(migrated: tuple[str, str]) -> None:
    with database_at_0006(migrated) as (engine, config):
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        with engine.connect() as conn:
            columns = {
                (t, c)
                for t, c in conn.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            }
            triggers = set(
                conn.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")).scalars()
            )
            functions = set(conn.execute(text("SELECT proname FROM pg_proc")).scalars())
        for gone in (
            ("event", "submitted_by"),
            ("event", "approved_by"),
            ("event", "image_exception"),
            ("event", "publish_at"),
            ("event", "published_rev"),
            ("event", "text_reviewed_rev"),
            ("event", "flyer_checked_at"),
            ("event_status_event", "four_eyes"),
            ("event_status_event", "submitted_by"),
            ("event_revision", "field_class"),
            ("organization", "trusted"),
        ):
            assert gone not in columns, gone
        for kept in (("event", "end_estimated"), ("event", "outcome"), ("event", "facts")):
            assert kept in columns, kept
        assert (
            not {"trg_event_enforce_publish_image", "trg_attachment_keep_published_poster"}
            & triggers
        )
        assert not {"enforce_publish_image", "keep_published_poster", "exception_ok"} & functions
        assert "attachment_poster_ok" in functions


def test_the_view_shows_published_and_archived_without_a_poster(migrated: tuple[str, str]) -> None:
    with database_at_0006(migrated) as (engine, config):
        seed_events(engine)
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT title, hero_sha FROM public_event_v ORDER BY title")
            ).all()
        assert [r[0] for r in rows] == ["E archived", "E followup", "E live"]
        assert all(r[1] is None for r in rows)


def test_the_downgrade_rebuilds_the_old_structure(migrated: tuple[str, str]) -> None:
    with database_at_0006(migrated) as (engine, config):
        seed_events(engine)
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
        command.downgrade(config, "0006_archive_feed")  # type: ignore[arg-type]
        with engine.connect() as conn:
            states = set(conn.execute(text("SELECT state FROM event")).scalars())
            has_trigger = conn.execute(
                text(
                    "SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_event_enforce_publish_image'"
                )
            ).scalar_one()
            trusted = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'organization' AND column_name = 'trusted'"
                )
            ).scalar_one()
        assert states <= {"idea", "live", "archived"} and has_trigger == 1 and trusted == 1
        command.upgrade(config, "0007_event_dossier")  # type: ignore[arg-type]
