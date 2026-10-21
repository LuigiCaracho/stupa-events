"""Archive, formats and feed: `format`, outcome and facts, full text search, the public view.

Revision ID: 0006_archive_feed
Revises: 0005_dossier_knowledge
Create Date: 2026-10-21 00:00:06

Adds `format` and the columns of M5 to `event` (format, template link, outcome, howto mark,
facts, location precision and its confirmation), makes `document.event_id` nullable with
`format_id` as the second owner (master howto), generates the `tsvector` columns with their
GIN and trigram indexes, adds the CHECKs against control characters on the taxonomy texts
(data steps first), widens the notification kinds and replaces `public_event_v` by the
feed view of M5. Data steps: free venue texts of public dossiers are confirmed as
`building` (contract 2.2, D1), control characters in taxonomy texts become spaces.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.modules.dossier.models_documents import DOCUMENT_SEARCH_TSV
from app.modules.events.models import CONTROL_CHARS, EVENT_SEARCH_TSV
from app.modules.formats.models import FORMAT_SEARCH_TSV, SLUG_PATTERN
from app.modules.formats.seed import seed_rows

revision: str = "0006_archive_feed"
down_revision: str | None = "0005_dossier_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_KINDS = (
    "'review_requested','changes_requested','comment_added','comment_resolved',"
    "'transition_done','task_assigned','checklist_due'"
)
_NEW_KINDS = _OLD_KINDS + ",'followup_reminder','auto_archived'"
_CLEAN_TEXTS = (
    ("organization", "name"),
    ("organization", "short"),
    ("category", "name"),
    ("category", "short"),
    ("venue", "city"),
    ("venue", "postcode"),
)

_VIEW_M5 = """
CREATE OR REPLACE VIEW public_event_v AS
SELECT e.id, e.slug, e.title, e.summary, e.starts_at, e.ends_at, e.all_day, e.tzid,
       e.public_status,
       o.id AS organization_id, o.slug AS organization_slug, o.name AS organization_name,
       o.short AS organization_short,
       CASE WHEN e.venue_id IS NOT NULL THEN CASE WHEN v.is_private THEN NULL ELSE v.name END
            WHEN e.location_precision <> 'hidden' THEN e.venue_text END AS venue_text,
       c.slug AS category_slug, c.name AS category_name, c.kind AS category_kind,
       a.sha256 AS hero_sha, a.derivatives AS hero_derivatives, a.alt_text AS hero_alt,
       a.credit AS hero_credit,
       e.updated_at, e.public_reason_code, e.public_reason_text,
       e.starts_on, e.ends_on, e.public_seq,
       p.slug AS category_parent_slug, p.name AS category_parent_name,
       p.kind AS category_parent_kind,
       f.slug AS format_slug, f.title AS format_title,
       CASE WHEN e.venue_id IS NOT NULL
                 THEN CASE WHEN v.is_private THEN 'Treffpunkt auf Anfrage' ELSE v.name END
            WHEN e.location_precision <> 'hidden' THEN e.venue_text END AS venue_name,
       CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.public_precision = 'exact'
            THEN v.address END AS venue_address,
       CASE WHEN v.id IS NOT NULL AND NOT v.is_private
                 AND v.public_precision IN ('exact', 'building')
            THEN v.city END AS venue_city,
       e.ticket_url, e.website_url, e.cost_text, e.description_md
FROM event e
JOIN organization o ON o.id = e.organization_id
LEFT JOIN category c ON c.id = e.primary_category_id
LEFT JOIN category p ON p.id = c.parent_id
LEFT JOIN format f ON f.id = e.format_id
LEFT JOIN venue v ON v.id = e.venue_id
LEFT JOIN attachment a ON a.id = e.hero_attachment_id AND a.event_id = e.id
    AND attachment_poster_ok(a)
WHERE e.state IN ('live', 'followup', 'archived') AND e.slug IS NOT NULL
  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))
"""

_VIEW_M3 = """
CREATE VIEW public_event_v AS
SELECT e.id, e.slug, e.title, e.summary, e.starts_at, e.ends_at, e.all_day, e.tzid,
       e.public_status,
       o.id AS organization_id, o.slug AS organization_slug, o.name AS organization_name,
       o.short AS organization_short,
       CASE WHEN e.venue_id IS NULL THEN e.venue_text WHEN v.is_private THEN NULL
            ELSE v.name END AS venue_text,
       c.slug AS category_slug, c.name AS category_name, c.kind AS category_kind,
       a.sha256 AS hero_sha, a.derivatives AS hero_derivatives, a.alt_text AS hero_alt,
       a.credit AS hero_credit,
       e.updated_at, e.public_reason_code, e.public_reason_text
FROM event e
JOIN organization o ON o.id = e.organization_id
LEFT JOIN category c ON c.id = e.primary_category_id
LEFT JOIN attachment a ON a.id = e.hero_attachment_id AND a.event_id = e.id
    AND attachment_poster_ok(a)
LEFT JOIN venue v ON v.id = e.venue_id
WHERE e.state IN ('live', 'followup', 'archived') AND e.slug IS NOT NULL
  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))
"""

_CATEGORY_VIEW = """
CREATE VIEW public_category_v AS
SELECT c.slug, c.name, c.kind, p.slug AS parent_slug
FROM category c LEFT JOIN category p ON p.id = c.parent_id
"""

_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
        REVOKE DELETE, TRUNCATE ON format FROM events_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        REVOKE ALL ON format FROM events_public;
        GRANT SELECT ON public_event_v, public_category_v TO events_public;
    END IF;
END $$;
"""

_VIEW_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        GRANT SELECT ON public_event_v TO events_public;
    END IF;
END $$;
"""

_LOCATION_DATA = """
UPDATE event
SET location_precision = 'building', location_confirmed_at = now(),
    location_confirmed_by = 'system:migration-0006'
WHERE venue_id IS NULL AND venue_text IS NOT NULL AND state IN ('live', 'followup', 'archived')
"""


def _format_table() -> None:
    op.create_table(
        "format",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("master_howto_document_id", sa.Uuid),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_verified_by", sa.Text),
        sa.Column("defaults", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("description_md", sa.Text),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("slug", name=op.f("uq_format_slug")),
        sa.CheckConstraint(f"slug ~ '{SLUG_PATTERN}'", name=op.f("ck_format_slug")),
        sa.CheckConstraint(
            f"char_length(title) BETWEEN 1 AND 120 AND title !~ '{CONTROL_CHARS}'",
            name=op.f("ck_format_title"),
        ),
        sa.CheckConstraint("jsonb_typeof(defaults) = 'object'", name=op.f("ck_format_defaults")),
        sa.CheckConstraint(
            "description_md IS NULL OR char_length(description_md) <= 20000",
            name=op.f("ck_format_description"),
        ),
    )
    op.create_index(op.f("ix_format_organization_id"), "format", ["organization_id"])
    _generated_tsv("format", FORMAT_SEARCH_TSV)
    _search_indexes("format")


def _generated_tsv(table: str, expression: str) -> None:
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN search_tsv tsvector "
        f"GENERATED ALWAYS AS ({expression}) STORED"
    )


def _search_indexes(table: str) -> None:
    op.execute(f"CREATE INDEX ix_{table}_search_tsv ON {table} USING gin (search_tsv)")
    op.execute(
        f"CREATE INDEX ix_{table}_title_trgm ON {table} "
        "USING gin (immutable_unaccent(title) gin_trgm_ops)"
    )


def _event_columns() -> None:
    op.add_column("event", sa.Column("format_id", sa.Uuid))
    op.add_column("event", sa.Column("derived_from_id", sa.Uuid))
    op.add_column("event", sa.Column("outcome", pg.JSONB))
    op.add_column("event", sa.Column("howto_verified_at", sa.DateTime(timezone=True)))
    op.add_column("event", sa.Column("howto_verified_by", sa.Text))
    op.add_column(
        "event",
        sa.Column("facts", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "event",
        sa.Column("location_precision", sa.Text, server_default="hidden", nullable=False),
    )
    op.add_column("event", sa.Column("location_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("event", sa.Column("location_confirmed_by", sa.Text))
    op.create_foreign_key(
        op.f("fk_event_format_id_format"),
        "event",
        "format",
        ["format_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_event_derived_from_id_event"),
        "event",
        "event",
        ["derived_from_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_event_format_id"), "event", ["format_id"])
    op.create_index(op.f("ix_event_derived_from_id"), "event", ["derived_from_id"])
    op.execute(_LOCATION_DATA)
    for name, expression in {
        "ck_event_location_precision": "location_precision IN ('exact', 'building', 'hidden')",
        "ck_event_derived_from_self": "derived_from_id <> id",
        "ck_event_outcome": "outcome IS NULL OR jsonb_typeof(outcome) = 'object'",
        "ck_event_facts": "jsonb_typeof(facts) = 'object'",
    }.items():
        op.create_check_constraint(op.f(name), "event", expression)
    _generated_tsv("event", EVENT_SEARCH_TSV)
    _search_indexes("event")


def _document_columns() -> None:
    op.alter_column("document", "event_id", nullable=True)
    op.add_column("document", sa.Column("format_id", sa.Uuid))
    op.create_foreign_key(
        op.f("fk_document_format_id_format"),
        "document",
        "format",
        ["format_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_format_master_howto_document_id_document"),
        "format",
        "document",
        ["master_howto_document_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_document_owner"), "document", "num_nonnulls(event_id, format_id) = 1"
    )
    op.create_check_constraint(
        op.f("ck_document_format_howto"), "document", "format_id IS NULL OR kind = 'howto'"
    )
    op.create_index(
        "uq_document_format_howto",
        "document",
        ["format_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'howto'"),
    )
    op.create_index(
        "uq_document_event_retrospective",
        "document",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'retrospective'"),
    )
    _generated_tsv("document", DOCUMENT_SEARCH_TSV)
    _search_indexes("document")


def _clean_taxonomy_texts() -> None:
    for table, column in _CLEAN_TEXTS:
        op.execute(
            f"UPDATE {table} SET {column} = regexp_replace({column}, '{CONTROL_CHARS}', ' ', 'g') "
            f"WHERE {column} ~ '{CONTROL_CHARS}'"
        )
        op.create_check_constraint(
            op.f(f"ck_{table}_{column}_clean"), table, f"{column} !~ '{CONTROL_CHARS}'"
        )


def _notification_kinds(kinds: str) -> None:
    for table in ("notification", "notification_pref"):
        name = f"ck_{table}_kind"
        op.drop_constraint(op.f(name), table)
        op.create_check_constraint(op.f(name), table, f"kind IN ({kinds})")


def _seed_formats() -> None:
    insert = sa.text(
        "INSERT INTO format (id, slug, title, organization_id, defaults, description_md, "
        "created_by) VALUES (:id, :slug, :title, :organization_id, CAST(:defaults AS jsonb), "
        ":description_md, 'system:seed') ON CONFLICT (slug) DO NOTHING"
    )
    for row in seed_rows():
        op.get_bind().execute(insert, row)


def upgrade() -> None:
    _format_table()
    _event_columns()
    _document_columns()
    _clean_taxonomy_texts()
    _notification_kinds(_NEW_KINDS)
    op.execute(_VIEW_M5)
    op.execute(_CATEGORY_VIEW)
    op.execute(_GRANTS)
    _seed_formats()


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_category_v")
    op.execute("DROP VIEW IF EXISTS public_event_v")
    op.execute(_VIEW_M3)
    op.execute(_VIEW_GRANT)
    op.execute("DELETE FROM notification_pref WHERE kind IN ('followup_reminder', 'auto_archived')")
    op.execute("DELETE FROM notification WHERE kind IN ('followup_reminder', 'auto_archived')")
    _notification_kinds(_OLD_KINDS)
    for table, column in reversed(_CLEAN_TEXTS):
        op.drop_constraint(op.f(f"ck_{table}_{column}_clean"), table)
    op.drop_constraint(op.f("fk_format_master_howto_document_id_document"), "format")
    op.execute("DROP INDEX IF EXISTS ix_document_title_trgm, ix_document_search_tsv")
    op.drop_column("document", "search_tsv")
    op.drop_index("uq_document_event_retrospective", "document")
    op.drop_index("uq_document_format_howto", "document")
    op.drop_constraint(op.f("ck_document_format_howto"), "document")
    op.drop_constraint(op.f("ck_document_owner"), "document")
    op.execute("ALTER TABLE document_revision DISABLE TRIGGER USER")
    op.execute(
        "DELETE FROM document_revision WHERE document_id IN "
        "(SELECT id FROM document WHERE event_id IS NULL)"
    )
    op.execute("ALTER TABLE document_revision ENABLE TRIGGER USER")
    op.execute("DELETE FROM document WHERE event_id IS NULL")
    op.drop_constraint(op.f("fk_document_format_id_format"), "document")
    op.drop_column("document", "format_id")
    op.alter_column("document", "event_id", nullable=False)
    op.execute("DROP INDEX IF EXISTS ix_event_title_trgm, ix_event_search_tsv")
    op.drop_column("event", "search_tsv")
    for name in (
        "ck_event_facts",
        "ck_event_outcome",
        "ck_event_derived_from_self",
        "ck_event_location_precision",
    ):
        op.drop_constraint(op.f(name), "event")
    op.drop_index(op.f("ix_event_derived_from_id"), "event")
    op.drop_index(op.f("ix_event_format_id"), "event")
    op.drop_constraint(op.f("fk_event_derived_from_id_event"), "event")
    op.drop_constraint(op.f("fk_event_format_id_format"), "event")
    for column in (
        "location_confirmed_by",
        "location_confirmed_at",
        "location_precision",
        "facts",
        "howto_verified_by",
        "howto_verified_at",
        "outcome",
        "derived_from_id",
        "format_id",
    ):
        op.drop_column("event", column)
    op.drop_table("format")
