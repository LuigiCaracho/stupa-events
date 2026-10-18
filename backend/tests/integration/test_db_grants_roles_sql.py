"""Least privilege as `deploy/db/roles.sql` really sets it (M1-KONTRAKT 3).

A fresh database `events` in the test container runs the file as superuser (stage 1),
then `alembic upgrade head` as `events_migrator`, then the file again (stage 2). The
tests connect as `events_app` and `events_public` and probe the grants with real SQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from tests.integration.conftest import make_alembic_config

pytestmark = pytest.mark.integration

ROLES_SQL = Path(__file__).resolve().parents[3] / "deploy" / "db" / "roles.sql"
ROLES = ("events_migrator", "events_app", "events_public")


def _swap(url: str, user: str, db: str) -> str:
    head, tail = url.split("@", 1)
    scheme = head.split("://", 1)[0]
    return f"{scheme}://{user}:pw@{tail.rsplit('/', 1)[0]}/{db}"


def _run_roles_sql(superuser: Engine) -> None:
    raw = superuser.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(ROLES_SQL.read_text(encoding="utf-8"))
        for role in ROLES:
            cur.execute(f"ALTER ROLE {role} PASSWORD 'pw'")
        raw.commit()
    finally:
        raw.close()


@pytest.fixture(scope="module")
def events_db(pg_urls: tuple[str, str]) -> Iterator[dict[str, Engine]]:
    sync_url = pg_urls[0]
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.exec_driver_sql("DROP DATABASE IF EXISTS events WITH (FORCE)")
        conn.exec_driver_sql("CREATE DATABASE events")
    admin.dispose()
    superuser = create_engine(sync_url.rsplit("/", 1)[0] + "/events")
    _run_roles_sql(superuser)
    migrator_async = _swap(pg_urls[1], "events_migrator", "events")
    command.upgrade(make_alembic_config(migrator_async), "head")
    _run_roles_sql(superuser)
    engines = {
        "superuser": superuser,
        "app": create_engine(_swap(sync_url, "events_app", "events")),
        "public": create_engine(_swap(sync_url, "events_public", "events")),
    }
    yield engines
    for eng in engines.values():
        eng.dispose()


def _fails(eng: Engine, statement: str) -> None:
    with pytest.raises(DBAPIError) as err, eng.begin() as conn:
        conn.exec_driver_sql(statement)
    assert "permission denied" in str(err.value) or "must be owner" in str(err.value)


def test_migrator_owns_every_table_and_view(events_db: dict[str, Engine]) -> None:
    with events_db["superuser"].connect() as conn:
        owners = conn.execute(
            text(
                "SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v')"
            )
        ).scalars()
        assert set(owners) == {"events_migrator"}


def test_public_role_reads_only_the_view(events_db: dict[str, Engine]) -> None:
    with events_db["public"].connect() as conn:
        conn.exec_driver_sql("SELECT count(*) FROM public_event_v").scalar_one()
    for table in ("event", "organization", "category", "attachment", "audit_entry"):
        with pytest.raises(ProgrammingError) as err, events_db["public"].connect() as conn:
            conn.exec_driver_sql(f"SELECT 1 FROM {table}")
        assert "InsufficientPrivilege" in type(err.value.orig).__name__


def test_app_role_has_no_delete_on_domain_tables(events_db: dict[str, Engine]) -> None:
    for table in ("event", "attachment", "organization", "category"):
        _fails(events_db["app"], f"DELETE FROM {table}")


def test_app_role_cannot_rewrite_history(events_db: dict[str, Engine]) -> None:
    for table in ("audit_entry", "event_revision", "event_status_event"):
        _fails(events_db["app"], f"UPDATE {table} SET id = id")
        _fails(events_db["app"], f"DELETE FROM {table}")
        _fails(events_db["app"], f"TRUNCATE {table}")


def test_app_role_has_no_ddl(events_db: dict[str, Engine]) -> None:
    _fails(events_db["app"], "CREATE TABLE sneaky (id int)")
    _fails(events_db["app"], "ALTER TABLE event DISABLE TRIGGER ALL")
    _fails(events_db["app"], "DROP VIEW public_event_v")


def test_app_role_deletes_sessions_and_reads_writes_events(events_db: dict[str, Engine]) -> None:
    with events_db["app"].begin() as conn:
        conn.exec_driver_sql("DELETE FROM auth_session")
        conn.exec_driver_sql("SELECT count(*) FROM event").scalar_one()
        conn.exec_driver_sql("UPDATE event SET title = title WHERE false")
