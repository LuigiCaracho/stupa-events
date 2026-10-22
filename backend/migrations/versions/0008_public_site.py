"""Public site: `category.description`, `search_tsv` on the event view, richer category view.

Revision ID: 0008_public_site
Revises: 0007_event_dossier
Create Date: 2026-10-22 00:00:08

The view `public_event_v` keeps its body and gets one column at the end, `search_tsv` (generated
from title, summary and description, all public fields), so the public search needs no table.
`public_category_v` gains `description`, `sort` and `active`. The downgrade drops and recreates
both views (Postgres cannot remove a column with `CREATE OR REPLACE`), then the column.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.modules.events.models import CONTROL_CHARS
from app.modules.taxonomy.reference_descriptions import DESCRIPTIONS

revision: str = "0008_public_site"
down_revision: str | None = "0007_event_dossier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = (
    "WHERE (e.state = 'published' OR (e.state = 'archived' AND e.published_at IS NOT NULL))\n"
    "  AND e.slug IS NOT NULL"
)
_CATEGORY_OLD = """
CREATE VIEW public_category_v AS
SELECT c.slug, c.name, c.kind, p.slug AS parent_slug
FROM category c LEFT JOIN category p ON p.id = c.parent_id
"""
_CATEGORY_NEW = """
CREATE OR REPLACE VIEW public_category_v AS
SELECT c.slug, c.name, c.kind, p.slug AS parent_slug, c.description, c.sort, c.active
FROM category c LEFT JOIN category p ON p.id = c.parent_id
"""
_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        GRANT SELECT ON public_event_v, public_category_v TO events_public;
    END IF;
END $$;
"""


def _view_body() -> str:
    """Read the view body of migration 0007, so the two never drift apart."""
    path = Path(__file__).with_name("0007_event_dossier.py")
    spec = importlib.util.spec_from_file_location("migration_0007", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._VIEW_BODY


def _event_view(body: str, *, replace: bool) -> str:
    verb = "CREATE OR REPLACE VIEW" if replace else "CREATE VIEW"
    return (
        f"{verb} public_event_v AS"
        + body.rstrip().replace("e.description_md\nFROM", "e.description_md, e.search_tsv\nFROM")
        + f"\n{_WHERE}"
    )


def upgrade() -> None:
    op.add_column("category", sa.Column("description", sa.Text()))
    op.create_check_constraint(
        op.f("ck_category_description_ok"),
        "category",
        "description IS NULL OR "
        f"(char_length(description) <= 300 AND description !~ '{CONTROL_CHARS}')",
    )
    body = _view_body()
    assert "e.description_md\nFROM" in body
    op.execute(_event_view(body, replace=True))
    op.execute(_CATEGORY_NEW)
    for slug, text in DESCRIPTIONS.items():
        op.execute(
            sa.text(
                "UPDATE category SET description = :t WHERE slug = :s AND description IS NULL"
            ).bindparams(t=text, s=slug)
        )
    op.execute(_GRANT)


def downgrade() -> None:
    op.execute("DROP VIEW public_category_v")
    op.execute("DROP VIEW public_event_v")
    body = _view_body()
    op.execute(f"CREATE VIEW public_event_v AS{body.rstrip()}\n{_WHERE}")
    op.execute(_CATEGORY_OLD)
    op.drop_constraint(op.f("ck_category_description_ok"), "category")
    op.drop_column("category", "description")
    op.execute(_GRANT)
