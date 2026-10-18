"""Least privilege of the runtime role on the baseline tables.

The test creates the roles the way `deploy/db/roles.sql` does (default privileges
without DELETE) and applies the baseline grants of the migration again.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


@pytest.fixture
def app_engine(migrated: tuple[str, str], engine: Engine) -> Iterator[Engine]:
    with engine.begin() as conn:
        for role in ("events_app", "events_audit_writer"):
            conn.execute(
                text(
                    f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') "
                    f"THEN CREATE ROLE {role} LOGIN PASSWORD 'pw'; END IF; END $$"
                )
            )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO events_app"))
        conn.execute(text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM events_app"))
        conn.execute(
            text("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO events_app")
        )
        conn.execute(text("GRANT DELETE ON auth_session TO events_app"))
        conn.execute(text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO events_app"))
        conn.execute(text("REVOKE UPDATE, DELETE, TRUNCATE ON audit_entry FROM events_app"))
    url = migrated[0].replace("test:test", "events_app:pw")
    eng = create_engine(url)
    yield eng
    eng.dispose()


def test_runtime_role_can_delete_sessions_but_nothing_in_the_audit_log(app_engine: Engine) -> None:
    with app_engine.begin() as conn:
        conn.execute(text("INSERT INTO principal (sub) VALUES ('s')"))
        conn.execute(
            text(
                "INSERT INTO auth_session (sid, principal_id, expires_at) "
                "SELECT 'x', id, now() + interval '1 day' FROM principal"
            )
        )
        conn.execute(text("DELETE FROM auth_session"))
        conn.execute(
            text("INSERT INTO audit_entry (action, hash) VALUES ('login', decode('00', 'hex'))")
        )
    for statement in (
        "UPDATE audit_entry SET action = 'x'",
        "DELETE FROM audit_entry",
        "TRUNCATE audit_entry",
        "DELETE FROM principal",
        "CREATE TABLE sneaky (id int)",
    ):
        with pytest.raises(DBAPIError), app_engine.begin() as conn:
            conn.execute(text(statement))
