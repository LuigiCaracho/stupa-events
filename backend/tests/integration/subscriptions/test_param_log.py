"""The address key must not reach the Postgres log, even when a statement with it fails.

Postgres logs the bind parameters of a failed statement (`DETAIL: parameters: ...`). The role
`events_subs` sets `log_parameter_max_length_on_error = 0` in `roles.sql`. A control run as the
superuser proves that the log would show the key otherwise. The test starts its own Postgres
with the `json-file` log driver, because the default driver of a machine may hide the log, and
switches the server-wide parameter logging on, so the role setting is what protects the key.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration
ROLES_SQL = Path(__file__).resolve().parents[4] / "deploy" / "db" / "roles.sql"


@pytest.fixture(scope="module")
def logged_postgres() -> Iterator[tuple[object, str]]:
    """Start Postgres with readable logs and the least-privilege roles; yield it and its host URL."""
    try:
        from docker.types import LogConfig
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed")
    container = PostgresContainer("postgres:16-alpine", driver="psycopg").with_kwargs(
        log_config=LogConfig(type=LogConfig.types.JSON)
    )
    try:
        container.start()
    except Exception as exc:  # pragma: no cover - environment without Docker
        pytest.skip(f"no Docker runtime: {exc}")
    try:
        url = container.get_connection_url()
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text("CREATE DATABASE events"))
            conn.execute(text("ALTER SYSTEM SET log_parameter_max_length_on_error = -1"))
            conn.execute(text("ALTER SYSTEM SET log_parameter_max_length = -1"))
            conn.execute(text("SELECT pg_reload_conf()"))
        admin.dispose()
        events_url = url.rsplit("/", 1)[0] + "/events"
        engine = create_engine(events_url)
        raw = engine.raw_connection()
        cur = raw.cursor()
        cur.execute("CREATE EXTENSION pgcrypto")
        cur.execute(ROLES_SQL.read_text(encoding="utf-8"))
        cur.execute("ALTER ROLE events_subs PASSWORD 'pw'")
        raw.commit()
        raw.close()
        engine.dispose()
        yield container, events_url
    finally:
        container.stop()


async def failing_decrypt(url: str, key: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(
                    text("SELECT pgp_sym_decrypt(:data, :key)").bindparams(
                        data=b"\x00\x01garbage", key=key
                    )
                )
    finally:
        await engine.dispose()


def async_url(url: str, user: str, password: str) -> str:
    head, tail = url.split("@", 1)
    scheme = head.split("://", 1)[0].replace("+psycopg", "+asyncpg")
    return f"{scheme}://{user}:{password}@{tail}"


async def test_the_subs_role_leaves_no_parameter_in_the_log_but_the_superuser_would(
    logged_postgres: tuple[object, str],
) -> None:
    container, url = logged_postgres
    secret = "PARAM-LOG-CANARY-" + "k" * 32
    await failing_decrypt(async_url(url, "events_subs", "pw"), secret + "-subs")
    await failing_decrypt(async_url(url, "test", "test"), secret + "-super")
    stdout, stderr = container.get_logs()  # type: ignore[attr-defined]
    log = (stdout + stderr).decode("utf-8", "replace")
    assert secret + "-super" in log, "control: the superuser's failed statement should log it"
    assert secret + "-subs" not in log


async def test_the_role_settings_are_zero(logged_postgres: tuple[object, str]) -> None:
    _, url = logged_postgres
    engine = create_async_engine(async_url(url, "events_subs", "pw"))
    try:
        async with engine.connect() as conn:
            for name in ("log_parameter_max_length", "log_parameter_max_length_on_error"):
                assert (await conn.execute(text(f"SHOW {name}"))).scalar_one() == "0"
    finally:
        await engine.dispose()
