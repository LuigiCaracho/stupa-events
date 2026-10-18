"""The database below the service: publish trigger, poster guard, append-only, grants."""

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


def new_event(engine: Engine, state: str = "in_review") -> str:
    with engine.begin() as conn:
        return str(conn.execute(text(INSERT_EVENT), {"state": state}).scalar_one())


def sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


@pytest.mark.parametrize("target", ["approved", "live"])
def test_direct_sql_publish_rejected(engine: Engine, target: str) -> None:
    event_id = new_event(engine)
    with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
        conn.execute(
            text("UPDATE event SET state = :s WHERE id = :id"), {"s": target, "id": event_id}
        )
    assert sqlstate(caught.value) == "23514"
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT state FROM event WHERE id = :id"), {"id": event_id}
            ).scalar_one()
            == "in_review"
        )


@pytest.mark.parametrize("target", ["approved", "live"])
def test_direct_sql_insert_in_a_published_state_is_rejected(engine: Engine, target: str) -> None:
    with pytest.raises(DBAPIError) as caught:
        new_event(engine, target)
    assert sqlstate(caught.value) == "23514"


def test_a_short_exception_reason_does_not_count(engine: Engine) -> None:
    event_id = new_event(engine)
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE event SET image_exception = '{\"reason\": \"kurz\"}', state = 'approved' WHERE id = :id"
            ),
            {"id": event_id},
        )


def test_a_valid_exception_lets_the_trigger_pass(engine: Engine) -> None:
    event_id = new_event(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                'UPDATE event SET image_exception = \'{"reason": "Hochschulveranstaltung"}\', '
                "state = 'live' WHERE id = :id"
            ),
            {"id": event_id},
        )


async def test_a_poster_that_is_not_ready_does_not_count_and_a_ready_one_does(
    api: Api, engine: Engine
) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    uploaded = await api.upload_poster("organizer-fsi", eid)
    attachment = uploaded.json()["id"]
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text("UPDATE event SET state = 'approved' WHERE id = :id"), {"id": eid})
    await api.process_poster(attachment)
    with engine.begin() as conn:
        conn.execute(text("UPDATE event SET state = 'live' WHERE id = :id"), {"id": eid})


async def test_the_poster_of_a_live_event_cannot_get_worse(api: Api, engine: Engine) -> None:
    event = await api.approved_ready_event()
    await api.fire("editor", event["id"], "T04")
    attachment = event["poster"]["id"]
    for statement in (
        "UPDATE attachment SET scan_status = 'infected' WHERE id = :id",
        "UPDATE attachment SET retired_at = now() WHERE id = :id",
        "UPDATE attachment SET derivatives = NULL WHERE id = :id",
        "UPDATE attachment SET rights_basis = 'unknown' WHERE id = :id",
        "UPDATE attachment SET alt_text = '' WHERE id = :id",
    ):
        with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
            conn.execute(text(statement), {"id": attachment})
        assert sqlstate(caught.value) == "23514", statement
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE attachment SET credit = 'Foto: Bea' WHERE id = :id"), {"id": attachment}
        )


async def test_the_poster_of_an_event_with_an_exception_may_change(
    api: Api, engine: Engine
) -> None:
    event = await api.approved_ready_event()
    await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/image-exception",
        json={"reason": "Ersatzmotiv fehlt"},
    )
    await api.fire("editor", event["id"], "T04")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE attachment SET scan_status = 'error' WHERE id = :id"),
            {"id": event["poster"]["id"]},
        )


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
            text(
                "INSERT INTO event_revision (event_id, rev, field_class, snapshot) "
                "VALUES (:id, 1, 'state', '{}')"
            ),
            {"id": event["id"]},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE event SET ends_at = starts_at - interval '1 hour'",
        "UPDATE event SET organization_id = NULL WHERE state <> 'idea'",
        "UPDATE event SET all_day = true",
        "UPDATE event SET title = E'zwei\\nZeilen'",
        "UPDATE event SET summary = E'Injektion\\r\\nBEGIN:VALARM'",
        "UPDATE event SET venue_text = 'a' || chr(8232) || 'b'",
        "UPDATE event SET state = 'published'",
        "UPDATE event SET rev = 0",
    ],
)
async def test_event_checks(api: Api, engine: Engine, statement: str) -> None:
    event = await api.create_event()
    await api.fire("organizer-fsi", event["id"], "T01")
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
            text(
                "INSERT INTO event_revision (event_id, rev, field_class, snapshot) VALUES (:id, 99, 'text', '{}')"
            ),
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


async def test_a_poster_of_a_foreign_event_does_not_count(api: Api, engine: Engine) -> None:
    donor = await api.approved_ready_event()
    other = new_event(engine)
    with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
        conn.execute(
            text("UPDATE event SET hero_attachment_id = :a, state = 'approved' WHERE id = :id"),
            {"a": donor["poster"]["id"], "id": other},
        )
    assert sqlstate(caught.value) == "23514"
