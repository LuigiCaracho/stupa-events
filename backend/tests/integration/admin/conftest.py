"""Fixtures of the admin integration tests (see `tests.integration.events.harness`).

The admin API creates and changes reference rows, which no other fixture wipes. The
autouse fixture puts the organizations, categories and venues back to the reference state
after each test.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text

from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS
from app.modules.taxonomy.venue_reference import VENUES
from tests.integration.events.harness import Api, api, clean_events, db_roles  # noqa: F401


@pytest.fixture(autouse=True)
def reference_state(engine: Engine) -> Iterator[None]:
    """Remove rows the test added and undo the flags it flipped, after the test."""
    yield
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        for table, rows in (
            ("organization", ORGANIZATIONS),
            ("category", CATEGORIES),
            ("venue", VENUES),
        ):
            ids = [str(row["id"]) for row in rows]
            conn.execute(text(f"DELETE FROM {table} WHERE id::text <> ALL(:ids)"), {"ids": ids})
        conn.execute(text("UPDATE organization SET trusted = (slug = 'stupa'), active = true"))
        conn.execute(text("UPDATE category SET active = true"))
        conn.execute(text("UPDATE venue SET active = true, is_private = false"))
