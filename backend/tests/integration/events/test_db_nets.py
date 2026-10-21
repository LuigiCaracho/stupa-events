"""The database below the service: checks, append-only history, the public view, grants."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration

INSERT_EVENT = (
    "INSERT INTO event (title, starts_at, ends_at, organization_id, created_by, state) "
    "SELECT 'Roh', now() + interval '2 days', now() + interval '3 days', id, 'sql', :state "
    "FROM organization WHERE slug = 'fsi' RETURNING id"
)


def new_event(engine: Engine, state: str = "draft") -> str:
    with engine.begin() as conn:
        return str(conn.execute(text(INSERT_EVENT), {"state": state}).scalar_one())


def sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def test_the_old_states_are_not_valid_any_more(engine: Engine) -> None:
    for state in ("idea", "planning", "in_review", "approved", "live", "followup", "withdrawn"):
        with pytest.raises(DBAPIError) as caught:
            new_event(engine, state)
        assert sqlstate(caught.value) == "23514", state


def test_a_draft_may_lack_the_organization_but_a_published_dossier_may_not(
    engine: Engine,
) -> None:
    event_id = new_event(engine)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE event SET organization_id = NULL WHERE id = :id"), {"id": event_id}
        )
    with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
        conn.execute(text("UPDATE event SET state = 'published' WHERE id = :id"), {"id": event_id})
    assert sqlstate(caught.value) == "23514"


@pytest.mark.parametrize("table", ["event_revision", "event_status_event"])
async def test_history_tables_are_append_only(api: Api, engine: Engine, table: str) -> None:
    await api.create_event()
    for statement in (
        f"UPDATE {table} SET actor_id = 'x'",
        f"DELETE FROM {table}",
        f"TRUNCATE {table}",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(text(statement))


async def test_revisions_are_unique_per_event(api: Api, engine: Engine) -> None:
    event = await api.create_event()
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("INSERT INTO event_revision (event_id, rev, snapshot) VALUES (:id, 1, '{}')"),
            {"id": event["id"]},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE event SET ends_at = starts_at - interval '1 hour'",
        "UPDATE event SET organization_id = NULL WHERE state <> 'draft'",
        "UPDATE event SET all_day = true",
        "UPDATE event SET title = E'zwei\\nZeilen'",
        "UPDATE event SET summary = E'Injektion\\r\\nBEGIN:VALARM'",
        "UPDATE event SET venue_text = 'a' || chr(8232) || 'b'",
        "UPDATE event SET state = 'live'",
        "UPDATE event SET tzid = 'UTC'",
        "UPDATE event SET rev = 0",
    ],
)
async def test_event_checks(api: Api, engine: Engine, statement: str) -> None:
    event = await api.to_state("published")
    assert event["state"] == "published"
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(statement))


def test_group_mapping_checks(engine: Engine) -> None:
    for group, role, org in (
        ("events-system:root", "admin", None),
        ("g1", "organizer", None),
        ("g2", "editor", "fsi"),
        ("g3", "root", None),
    ):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO group_mapping (oidc_group, role, organization_id) "
                    "VALUES (:g, :r, (SELECT id FROM organization WHERE slug = :o))"
                ),
                {"g": group, "r": role, "o": org},
            )


@pytest.fixture
def app_engine(db_roles: tuple[str, str]) -> Engine:
    return create_engine(db_roles[0])


@pytest.fixture
def public_engine(db_roles: tuple[str, str]) -> Engine:
    return create_engine(db_roles[1])


async def test_db_grants_runtime_role(api: Api, app_engine: Engine) -> None:
    event = await api.create_event()
    with app_engine.begin() as conn:
        conn.execute(text("UPDATE event SET summary = 'ok' WHERE id = :id"), {"id": event["id"]})
        conn.execute(
            text("INSERT INTO event_revision (event_id, rev, snapshot) VALUES (:id, 99, '{}')"),
            {"id": event["id"]},
        )
    for statement in (
        "DELETE FROM event",
        "DELETE FROM attachment",
        "DELETE FROM organization",
        "UPDATE event_revision SET actor_id = 'x'",
        "UPDATE event_status_event SET actor_id = 'x'",
        "DELETE FROM event_revision",
        "UPDATE audit_entry SET action = 'x'",
        "CREATE TABLE sneaky (id int)",
        "TRUNCATE event",
    ):
        with pytest.raises(DBAPIError), app_engine.begin() as conn:
            conn.execute(text(statement))


async def test_db_grants_public_role_reads_only_the_view(api: Api, public_engine: Engine) -> None:
    with public_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM public_event_v")).scalar_one() == 0
    for table in ("event", "organization", "category", "attachment", "principal", "audit_entry"):
        with pytest.raises(DBAPIError) as caught, public_engine.connect() as conn:
            conn.execute(text(f"SELECT * FROM {table}"))
        assert sqlstate(caught.value) == "42501", table
    with pytest.raises(DBAPIError), public_engine.begin() as conn:
        conn.execute(text("DELETE FROM public_event_v"))


def test_a_poster_of_depicted_persons_needs_a_consent_note_to_reach_the_view(
    engine: Engine,
) -> None:
    event_id = new_event(engine)
    with engine.begin() as conn:
        attachment = conn.execute(
            text(
                "INSERT INTO attachment (event_id, display_name, storage_name, mime, size_bytes, sha256, "
                "scan_status, kind, rights_basis, persons_depicted, consent_note, derivatives) "
                "VALUES (:e, 'p', 'p', 'image/png', 1, 'aa', 'clean', 'poster', 'unknown', true, NULL, "
                '\'{"thumb_400": {}, "card_1200": {}, "og_1200x630": {}}\') RETURNING id'
            ),
            {"e": event_id},
        ).scalar_one()
        conn.execute(
            text(
                "UPDATE event SET hero_attachment_id = :a, state = 'published', slug = 'rohling' "
                "WHERE id = :e"
            ),
            {"a": attachment, "e": event_id},
        )
    hero = "SELECT hero_sha FROM public_event_v WHERE id = :e"
    with engine.connect() as conn:
        assert conn.execute(text(hero), {"e": event_id}).scalar_one() is None
    with engine.begin() as conn:
        conn.execute(text("UPDATE attachment SET consent_note = 'liegt vor'"))
    with engine.connect() as conn:
        assert conn.execute(text(hero), {"e": event_id}).scalar_one() == "aa"


def test_the_new_event_columns_are_checked(engine: Engine) -> None:
    event_id = new_event(engine)
    bad = [
        "ticket_url = 'http://x.de'",
        "website_url = 'https://user@x.de'",
        "public_reason_code = 'nonsense'",
        "public_status = 'scheduled', public_reason_code = 'room'",
        "cost_text = repeat('x', 201)",
        "public_reason_text = repeat('x', 141), public_status = 'cancelled'",
    ]
    for assignment in bad:
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(text(f"UPDATE event SET {assignment} WHERE id = :e"), {"e": event_id})
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE event SET ticket_url = 'https://t.example.org/x', public_status = 'cancelled', "
                "public_reason_code = 'room' WHERE id = :e"
            ),
            {"e": event_id},
        )


def test_events_public_reads_the_view_only_and_the_runtime_role_deletes_drafts(
    db_roles: tuple[str, str], engine: Engine
) -> None:
    from sqlalchemy import create_engine

    app = create_engine(db_roles[0])
    public = create_engine(db_roles[1])
    try:
        with app.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO editor_draft (owner_kind, owner_id, principal_sub, base_rev, fields) "
                    "VALUES ('event', gen_random_uuid(), 's', 1, '{}')"
                )
            )
            conn.execute(text("DELETE FROM editor_draft"))
            with pytest.raises(DBAPIError):
                conn.execute(text("DELETE FROM event"))
        with pytest.raises(DBAPIError), public.begin() as conn:
            conn.execute(text("SELECT * FROM editor_draft"))
    finally:
        app.dispose()
        public.dispose()
