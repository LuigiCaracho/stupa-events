"""Least privilege of the runtime role on the M4 and M5 tables (E27: no delete on dossier data, formats)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration

NO_DELETE = ("attachment", "document", "document_revision", "comment", "quote", "format")
MAY_DELETE = ("checklist_item", "notification", "markdown_image", "media_ref", "editor_draft")


@pytest.fixture
def app_engine(db_roles: tuple[str, str], engine: Engine) -> Iterator[Engine]:
    eng = create_engine(db_roles[0])
    yield eng
    eng.dispose()


@pytest.mark.parametrize("table", NO_DELETE)
def test_the_runtime_role_cannot_delete_dossier_data(app_engine: Engine, table: str) -> None:
    with pytest.raises(DBAPIError, match="permission denied"), app_engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))


@pytest.mark.parametrize("table", MAY_DELETE)
def test_the_runtime_role_may_delete_working_data(app_engine: Engine, table: str) -> None:
    with app_engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))


def test_revisions_cannot_be_updated_by_the_runtime_role(app_engine: Engine) -> None:
    with pytest.raises(DBAPIError, match="permission denied"), app_engine.begin() as conn:
        conn.execute(text("UPDATE document_revision SET title = 'x'"))


def test_the_public_role_reads_the_views_and_nothing_else(
    db_roles: tuple[str, str], engine: Engine
) -> None:
    public = create_engine(db_roles[1])
    try:
        with public.begin() as conn:
            conn.execute(text("SELECT count(*) FROM public_event_v"))
            conn.execute(text("SELECT count(*) FROM public_category_v"))
        for table in ("event", "document", "attachment", "format", "venue", "category"):
            with pytest.raises(DBAPIError, match="permission denied"), public.begin() as conn:
                conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    finally:
        public.dispose()
