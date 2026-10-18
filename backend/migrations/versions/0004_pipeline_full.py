"""Full pipeline: event columns, Four-Eyes net, `editor_draft`, rights rule, public view.

Revision ID: 0004_pipeline_full
Revises: 0003_roles_taxonomy
Create Date: 2026-10-18 00:00:04

Adds the columns of M3 to `event` (links, cost text, `venue_id`, `publish_at`, the public
reason, `end_estimated`, the review markers), the Four-Eyes columns and CHECK on
`event_status_event`, the table `editor_draft`, the consent rule in `attachment_poster_ok`
and the extended view `public_event_v`. Every new column is nullable or has a default, so
existing rows stay valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.modules.events.models import CONTROL_CHARS

revision: str = "0004_pipeline_full"
down_revision: str | None = "0003_roles_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REASONS = "'none','room','speaker','illness','registration','weather','other'"
_URL = r"~ '^https://[^/@\s]+\.[^/@\s]+' AND length({c}) <= 500 AND {c} !~ '" + CONTROL_CHARS + "'"

_POSTER_OK = """
CREATE OR REPLACE FUNCTION attachment_poster_ok(a attachment) RETURNS boolean
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT a.kind = 'poster'
        AND a.scan_status = 'clean'
        AND a.retired_at IS NULL
        AND coalesce(a.alt_text, '') <> ''
        AND coalesce(a.credit, '') <> ''
        AND a.rights_basis <> 'unknown'
        AND (NOT a.persons_depicted OR btrim(coalesce(a.consent_note, '')) <> '')
        AND a.derivatives IS NOT NULL
        AND a.derivatives ?& ARRAY['thumb_400', 'card_1200', 'og_1200x630'] $$
"""

_POSTER_OK_M2 = _POSTER_OK.replace(
    "        AND (NOT a.persons_depicted OR btrim(coalesce(a.consent_note, '')) <> '')\n", ""
)

_VIEW_COLUMNS = """
SELECT e.id,
       e.slug,
       e.title,
       e.summary,
       e.starts_at,
       e.ends_at,
       e.all_day,
       e.tzid,
       e.public_status,
       o.id AS organization_id,
       o.slug AS organization_slug,
       o.name AS organization_name,
       o.short AS organization_short,
       {venue} AS venue_text,
       c.slug AS category_slug,
       c.name AS category_name,
       c.kind AS category_kind,
       a.sha256 AS hero_sha,
       a.derivatives AS hero_derivatives,
       a.alt_text AS hero_alt,
       a.credit AS hero_credit,
       e.updated_at{extra}
FROM event e
JOIN organization o ON o.id = e.organization_id
LEFT JOIN category c ON c.id = e.primary_category_id
LEFT JOIN attachment a ON a.id = e.hero_attachment_id AND a.event_id = e.id
    AND attachment_poster_ok(a){join}
WHERE e.state IN ('live', 'followup', 'archived')
  AND e.slug IS NOT NULL
  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))
"""

_VIEW_M3 = "CREATE OR REPLACE VIEW public_event_v AS" + _VIEW_COLUMNS.format(
    venue=(
        "CASE WHEN e.venue_id IS NULL THEN e.venue_text WHEN v.is_private THEN NULL ELSE v.name END"
    ),
    extra=",\n       e.public_reason_code,\n       e.public_reason_text",
    join="\nLEFT JOIN venue v ON v.id = e.venue_id",
)
_VIEW_M2 = "CREATE VIEW public_event_v AS" + _VIEW_COLUMNS.format(
    venue="e.venue_text", extra="", join=""
)

_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON editor_draft TO events_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        REVOKE ALL ON editor_draft FROM events_public;
    END IF;
END $$;
"""

_EVENT_COLUMNS = (
    "ticket_url",
    "website_url",
    "cost_text",
    "venue_id",
    "publish_at",
    "public_reason_code",
    "public_reason_text",
    "end_estimated",
    "flyer_checked_at",
    "text_reviewed_rev",
    "published_rev",
)


def _event_columns() -> None:
    op.add_column("event", sa.Column("ticket_url", sa.Text))
    op.add_column("event", sa.Column("website_url", sa.Text))
    op.add_column("event", sa.Column("cost_text", sa.Text))
    op.add_column("event", sa.Column("venue_id", sa.Uuid))
    op.add_column("event", sa.Column("publish_at", sa.DateTime(timezone=True)))
    op.add_column(
        "event", sa.Column("public_reason_code", sa.Text, server_default="none", nullable=False)
    )
    op.add_column("event", sa.Column("public_reason_text", sa.Text))
    op.add_column(
        "event",
        sa.Column("end_estimated", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )
    op.add_column("event", sa.Column("flyer_checked_at", sa.DateTime(timezone=True)))
    op.add_column(
        "event", sa.Column("text_reviewed_rev", sa.Integer, server_default="0", nullable=False)
    )
    op.add_column("event", sa.Column("published_rev", sa.Integer))
    op.create_foreign_key(
        op.f("fk_event_venue_id_venue"), "event", "venue", ["venue_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_event_venue_id"), "event", ["venue_id"])
    checks = {
        "ck_event_ticket_url": "ticket_url IS NULL OR ticket_url " + _URL.format(c="ticket_url"),
        "ck_event_website_url": "website_url IS NULL OR website_url "
        + _URL.format(c="website_url"),
        "ck_event_cost_text": "cost_text IS NULL OR "
        f"(length(cost_text) <= 200 AND cost_text !~ '{CONTROL_CHARS}')",
        "ck_event_public_reason_code": f"public_reason_code IN ({_REASONS})",
        "ck_event_public_reason_text": "public_reason_text IS NULL OR "
        f"(length(public_reason_text) <= 140 AND public_reason_text !~ '{CONTROL_CHARS}')",
        "ck_event_public_reason_scheduled": "public_status <> 'scheduled' OR "
        "(public_reason_code = 'none' AND public_reason_text IS NULL)",
    }
    for name, expression in checks.items():
        op.create_check_constraint(op.f(name), "event", expression)


def _status_event_columns() -> None:
    op.add_column(
        "event_status_event",
        sa.Column("four_eyes", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )
    op.add_column("event_status_event", sa.Column("submitted_by", sa.Text))
    op.create_check_constraint(
        op.f("ck_event_status_event_four_eyes"),
        "event_status_event",
        "transition_id <> 'T04' OR NOT four_eyes OR "
        "(submitted_by IS NOT NULL AND actor_id IS DISTINCT FROM submitted_by)",
    )


def _editor_draft() -> None:
    op.create_table(
        "editor_draft",
        sa.Column("owner_kind", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Uuid, nullable=False),
        sa.Column("principal_sub", sa.Text, nullable=False),
        sa.Column("base_rev", sa.Integer, nullable=False),
        sa.Column("fields", pg.JSONB, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("owner_kind", "owner_id", "principal_sub", name="pk_editor_draft"),
        sa.CheckConstraint("owner_kind IN ('event')", name="ck_editor_draft_owner_kind"),
    )
    op.create_index("ix_editor_draft_updated_at", "editor_draft", ["updated_at"])


def upgrade() -> None:
    _event_columns()
    _status_event_columns()
    _editor_draft()
    op.execute(_POSTER_OK)
    op.execute(_VIEW_M3)
    op.execute(_GRANTS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_event_v")
    op.execute(_VIEW_M2)
    op.execute(_POSTER_OK_M2)
    op.drop_table("editor_draft")
    op.drop_constraint(op.f("ck_event_status_event_four_eyes"), "event_status_event")
    op.drop_column("event_status_event", "submitted_by")
    op.drop_column("event_status_event", "four_eyes")
    for name in (
        "ck_event_public_reason_scheduled",
        "ck_event_public_reason_text",
        "ck_event_public_reason_code",
        "ck_event_cost_text",
        "ck_event_website_url",
        "ck_event_ticket_url",
    ):
        op.drop_constraint(op.f(name), "event")
    op.drop_index(op.f("ix_event_venue_id"), "event")
    op.drop_constraint(op.f("fk_event_venue_id_venue"), "event", type_="foreignkey")
    for column in reversed(_EVENT_COLUMNS):
        op.drop_column("event", column)
