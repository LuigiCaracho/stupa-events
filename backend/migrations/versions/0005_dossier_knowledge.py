"""Dossier and knowledge: attachment kinds and limits, documents, comments, checklists, quotes.

Revision ID: 0005_dossier_knowledge
Revises: 0004_pipeline_full
Create Date: 2026-10-19 00:00:05

Reworks `attachment` (new kinds, limits per type, the "never shared" net, flyer and preview
columns) and adds `document`, `document_revision`, `comment`, `checklist_template(_item)`,
`checklist_item`, `quote`, `notification`, `notification_pref` and `media_ref`. Data steps
run before the new CHECKs, so existing rows stay valid. The checklist templates come from
`seeds/checklists.yaml`; `media_ref` is backfilled from the description texts and the
revision snapshots so that the first garbage collection keeps every image in use.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.modules.dossier.checklist_seed import read_seed
from app.modules.dossier.models_comments import ANCHOR_CHECK

revision: str = "0005_dossier_knowledge"
down_revision: str | None = "0004_pipeline_full"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = "'poster','social_post','business_plan','quote','contract','howto_file','other'"
_OLD_KINDS = (
    "'poster','social_post','poster_print','businessplan','quote','contract',"
    "'mail_attachment','other'"
)
_NOTIFICATION_KINDS = (
    "'review_requested','changes_requested','comment_added','comment_resolved',"
    "'transition_done','task_assigned','checklist_due'"
)
_UUID_RE = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

_COMMENT_GUARD = """
CREATE FUNCTION comment_immutable_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'comment is append-only; DELETE denied'
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF (to_jsonb(NEW) - 'resolved_at' - 'resolved_by')
        IS DISTINCT FROM (to_jsonb(OLD) - 'resolved_at' - 'resolved_by') THEN
        RAISE EXCEPTION 'comment is append-only; only the resolution may change'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

_BACKFILL_MEDIA = f"""
INSERT INTO media_ref (image_id, owner_type, owner_id)
SELECT DISTINCT m.id, 'event', src.event_id
FROM (
    SELECT e.id AS event_id, e.description_md AS body FROM event e
    UNION ALL
    SELECT r.event_id, r.snapshot ->> 'description_md' FROM event_revision r
) src
CROSS JOIN LATERAL regexp_matches(
    src.body, '\\]\\(/api/media/images/({_UUID_RE})\\)', 'g') AS hit(groups)
JOIN markdown_image m ON m.id = hit.groups[1]::uuid
WHERE src.body IS NOT NULL
ON CONFLICT DO NOTHING
"""

_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
        REVOKE UPDATE, TRUNCATE ON document_revision FROM events_app;
        REVOKE DELETE, TRUNCATE ON document, document_revision, comment, quote,
            checklist_template, checklist_template_item FROM events_app;
        GRANT DELETE ON checklist_item, notification, markdown_image, media_ref TO events_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        REVOKE ALL ON document, document_revision, comment, quote, checklist_template,
            checklist_template_item, checklist_item, notification, notification_pref,
            media_ref FROM events_public;
    END IF;
END $$;
"""


def _ts(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if default else None,
        nullable=nullable,
    )


def _pk() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _event_fk() -> sa.Column:
    return sa.Column(
        "event_id", sa.Uuid, sa.ForeignKey("event.id", ondelete="RESTRICT"), nullable=False
    )


def _attachment() -> None:
    op.drop_constraint(op.f("ck_attachment_ck_attachment_kind"), "attachment")
    op.drop_constraint(op.f("ck_attachment_ck_attachment_size_limit"), "attachment")
    op.execute("UPDATE attachment SET kind = 'business_plan' WHERE kind = 'businessplan'")
    op.execute(
        "UPDATE attachment SET kind = 'other' WHERE kind IN ('poster_print', 'mail_attachment')"
    )
    op.execute(
        "UPDATE attachment SET visibility = 'org' "
        "WHERE kind IN ('quote', 'business_plan', 'contract') AND visibility = 'shared'"
    )
    op.create_check_constraint(op.f("ck_attachment_kind"), "attachment", f"kind IN ({_KINDS})")
    op.create_check_constraint(
        op.f("ck_attachment_size"),
        "attachment",
        "size_bytes <= CASE WHEN mime LIKE 'image/%' THEN 10485760 ELSE 26214400 END",
    )
    op.create_check_constraint(
        op.f("ck_attachment_restricted_not_shared"),
        "attachment",
        "kind NOT IN ('quote', 'business_plan', 'contract') OR visibility <> 'shared'",
    )
    op.add_column(
        "attachment",
        sa.Column("contains_date", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )
    op.add_column("attachment", sa.Column("dated_for", sa.Date))
    op.add_column("attachment", sa.Column("flyer_date_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("attachment", sa.Column("flyer_date_confirmed_by", sa.Text))
    op.add_column("attachment", sa.Column("preview_key", sa.Text))
    op.create_index(
        "ix_attachment_event_kind",
        "attachment",
        ["event_id", "kind"],
        postgresql_where=sa.text("retired_at IS NULL"),
    )


def _documents() -> None:
    op.create_table(
        "document",
        _pk(),
        _event_fk(),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body_md", sa.Text, server_default="", nullable=False),
        sa.Column("meta", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("visibility", sa.Text, server_default="org", nullable=False),
        sa.Column("carry_over", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("rev", sa.Integer, server_default="1", nullable=False),
        _ts("verified_at", nullable=True, default=False),
        sa.Column("verified_by", sa.Text),
        sa.Column("created_by", sa.Text),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "kind IN ('howto', 'retrospective', 'notes', 'mail_template')", name="kind"
        ),
        sa.CheckConstraint("visibility IN ('team', 'org', 'shared')", name="visibility"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title"),
        sa.CheckConstraint("char_length(body_md) <= 200000", name="body_md"),
    )
    op.create_index("ix_document_event_id", "document", ["event_id"])
    op.create_index(
        "uq_document_event_howto",
        "document",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'howto'"),
    )
    op.create_table(
        "document_revision",
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("document.id", ondelete="RESTRICT")),
        sa.Column("rev", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body_md", sa.Text, nullable=False),
        sa.Column("meta", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("actor_id", sa.Text),
        sa.Column("actor_type", sa.Text, server_default="human", nullable=False),
        sa.Column("change_note", sa.Text),
        _ts("at"),
        sa.PrimaryKeyConstraint("document_id", "rev", name="pk_document_revision"),
        sa.CheckConstraint("actor_type IN ('human', 'agent', 'system')", name="actor_type"),
        sa.CheckConstraint(
            "change_note IS NULL OR char_length(change_note) <= 500",
            name="note",
        ),
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER trg_document_revision_no_{operation.lower()} "
            f"BEFORE {operation} ON document_revision "
            "FOR EACH ROW EXECUTE FUNCTION append_only_guard()"
        )
    op.execute(
        "CREATE TRIGGER trg_document_revision_no_truncate BEFORE TRUNCATE ON document_revision "
        "FOR EACH STATEMENT EXECUTE FUNCTION append_only_guard()"
    )
    op.drop_constraint(op.f("ck_editor_draft_ck_editor_draft_owner_kind"), "editor_draft")
    op.create_check_constraint(
        op.f("ck_editor_draft_owner_kind"), "editor_draft", "owner_kind IN ('event', 'document')"
    )


def _comments() -> None:
    op.create_table(
        "comment",
        _pk(),
        _event_fk(),
        sa.Column("parent_id", sa.Uuid, sa.ForeignKey("comment.id", ondelete="RESTRICT")),
        sa.Column("author_sub", sa.Text, nullable=False),
        sa.Column("actor_type", sa.Text, server_default="human", nullable=False),
        sa.Column("body_md", sa.Text, nullable=False),
        sa.Column("anchor", pg.JSONB),
        _ts("resolved_at", nullable=True, default=False),
        sa.Column("resolved_by", sa.Text),
        _ts("created_at"),
        sa.CheckConstraint("actor_type IN ('human', 'agent', 'system')", name="actor_type"),
        sa.CheckConstraint("char_length(body_md) BETWEEN 1 AND 4000", name="body_md"),
        sa.CheckConstraint(ANCHOR_CHECK, name="anchor"),
    )
    op.create_index("ix_comment_event_id", "comment", ["event_id"])
    op.create_index(
        "ix_comment_open",
        "comment",
        ["event_id"],
        postgresql_where=sa.text("resolved_at IS NULL AND parent_id IS NULL"),
    )
    op.execute(_COMMENT_GUARD)
    op.execute(
        "CREATE TRIGGER trg_comment_immutable BEFORE UPDATE OR DELETE ON comment "
        "FOR EACH ROW EXECUTE FUNCTION comment_immutable_guard()"
    )


def _checklists() -> None:
    phase = "phase IN ('planning', 'review', 'live', 'followup')"
    op.create_table(
        "checklist_template",
        _pk(),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category_id", sa.Uuid, sa.ForeignKey("category.id", ondelete="RESTRICT")),
        sa.Column("profile", sa.Text),
        sa.UniqueConstraint("slug", name="uq_checklist_template_slug"),
        sa.CheckConstraint(
            "profile IS NULL OR profile IN ('generic', 'party', 'meeting', 'trip')",
            name="profile",
        ),
        sa.CheckConstraint("num_nonnulls(category_id, profile) <= 1", name="owner"),
    )
    template_item = op.create_table(
        "checklist_template_item",
        _pk(),
        sa.Column(
            "template_id",
            sa.Uuid,
            sa.ForeignKey("checklist_template.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("phase", sa.Text, nullable=False),
        sa.Column("required", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("due_offset_days", sa.Integer),
        sa.UniqueConstraint("template_id", "key", name="uq_checklist_template_item_key"),
        sa.CheckConstraint(phase, name="phase"),
        sa.CheckConstraint("due_offset_days BETWEEN -365 AND 365", name="offset"),
    )
    op.create_table(
        "checklist_item",
        _pk(),
        _event_fk(),
        sa.Column(
            "template_item_id",
            sa.Uuid,
            sa.ForeignKey("checklist_template_item.id", ondelete="RESTRICT"),
        ),
        sa.Column("position", sa.Text(collation="C"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("phase", sa.Text, nullable=False),
        sa.Column("required", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("assignee_sub", sa.Text),
        sa.Column("due_offset_days", sa.Integer),
        _ts("due_at", nullable=True, default=False),
        sa.Column("due_manual", sa.Boolean, server_default=sa.text("false"), nullable=False),
        _ts("done_at", nullable=True, default=False),
        sa.Column("done_by", sa.Text),
        sa.Column("waived_reason", sa.Text),
        sa.Column("notified_due_for", sa.Date),
        sa.Column("created_by", sa.Text),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("event_id", "template_item_id", name="uq_checklist_item_template"),
        sa.CheckConstraint(phase, name="phase"),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 200", name="text"),
        sa.CheckConstraint("done_at IS NULL OR waived_reason IS NULL", name="done_or_waived"),
        sa.CheckConstraint(
            "waived_reason IS NULL OR btrim(waived_reason) <> ''",
            name="waived_reason",
        ),
    )
    op.create_index("ix_checklist_item_event_phase", "checklist_item", ["event_id", "phase"])
    op.create_index(
        "ix_checklist_item_assignee_open",
        "checklist_item",
        ["assignee_sub"],
        postgresql_where=sa.text("done_at IS NULL AND waived_reason IS NULL"),
    )
    templates, items = read_seed()
    template_table = sa.table(
        "checklist_template",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.Text),
        sa.column("name", sa.Text),
        sa.column("profile", sa.Text),
    )
    op.bulk_insert(template_table, templates)
    op.bulk_insert(template_item, items)


def _quotes() -> None:
    op.create_table(
        "quote",
        _pk(),
        _event_fk(),
        sa.Column("grp", sa.Text, nullable=False),
        sa.Column("vendor", sa.Text, nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.Text, server_default="EUR", nullable=False),
        sa.Column("valid_until", sa.Date),
        sa.Column("selected", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("attachment_id", sa.Uuid, sa.ForeignKey("attachment.id", ondelete="RESTRICT")),
        sa.Column("created_by", sa.Text),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("retired_at", nullable=True, default=False),
        sa.CheckConstraint("amount_cents >= 0", name="amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        sa.CheckConstraint("char_length(grp) BETWEEN 1 AND 60", name="grp"),
        sa.CheckConstraint("char_length(vendor) BETWEEN 1 AND 120", name="vendor"),
        sa.CheckConstraint("note IS NULL OR char_length(note) <= 500", name="note"),
    )
    op.create_index("ix_quote_event_id", "quote", ["event_id"])
    op.create_index(
        "uq_quote_selected",
        "quote",
        ["event_id", "grp"],
        unique=True,
        postgresql_where=sa.text("selected AND retired_at IS NULL"),
    )


def _notifications() -> None:
    op.create_table(
        "notification",
        _pk(),
        sa.Column("recipient_sub", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("event_id", sa.Uuid, sa.ForeignKey("event.id", ondelete="RESTRICT")),
        sa.Column("params", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("link", sa.Text, nullable=False),
        sa.Column("dedupe_key", sa.Text),
        _ts("created_at"),
        _ts("read_at", nullable=True, default=False),
        sa.UniqueConstraint("dedupe_key", name="uq_notification_dedupe_key"),
        sa.CheckConstraint(f"kind IN ({_NOTIFICATION_KINDS})", name="kind"),
        sa.CheckConstraint(r"link ~ '^/[^/\\]'", name="link"),
    )
    op.create_index(
        "ix_notification_recipient_sub_created_at",
        "notification",
        ["recipient_sub", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_notification_unread",
        "notification",
        ["recipient_sub"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_table(
        "notification_pref",
        sa.Column("principal_sub", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("in_app", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("mail", sa.Boolean, server_default=sa.text("true"), nullable=False),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("principal_sub", "kind", name="pk_notification_pref"),
        sa.CheckConstraint(f"kind IN ({_NOTIFICATION_KINDS})", name="kind"),
    )


def _media() -> None:
    op.add_column("markdown_image", sa.Column("gc_marked_at", sa.DateTime(timezone=True)))
    op.create_table(
        "media_ref",
        sa.Column(
            "image_id",
            sa.Uuid,
            sa.ForeignKey("markdown_image.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_type", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Uuid, nullable=False),
        sa.PrimaryKeyConstraint("image_id", "owner_type", "owner_id", name="pk_media_ref"),
        sa.CheckConstraint(
            "owner_type IN ('event', 'document', 'comment', 'draft')", name="owner_type"
        ),
    )
    op.execute(_BACKFILL_MEDIA)


def upgrade() -> None:
    _attachment()
    _documents()
    _comments()
    _checklists()
    _quotes()
    _notifications()
    _media()
    op.execute(_GRANTS)


def downgrade() -> None:
    for table in (
        "media_ref",
        "notification_pref",
        "notification",
        "quote",
        "checklist_item",
        "checklist_template_item",
        "checklist_template",
        "comment",
        "document_revision",
        "document",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS comment_immutable_guard()")
    op.drop_column("markdown_image", "gc_marked_at")
    op.execute("DELETE FROM editor_draft WHERE owner_kind = 'document'")
    op.drop_constraint(op.f("ck_editor_draft_owner_kind"), "editor_draft")
    op.create_check_constraint(
        op.f("ck_editor_draft_owner_kind"), "editor_draft", "owner_kind IN ('event')"
    )
    op.drop_index("ix_attachment_event_kind", "attachment")
    for column in (
        "preview_key",
        "flyer_date_confirmed_by",
        "flyer_date_confirmed_at",
        "dated_for",
        "contains_date",
    ):
        op.drop_column("attachment", column)
    op.drop_constraint(op.f("ck_attachment_restricted_not_shared"), "attachment")
    op.drop_constraint(op.f("ck_attachment_size"), "attachment")
    op.drop_constraint(op.f("ck_attachment_kind"), "attachment")
    op.execute("UPDATE attachment SET kind = 'businessplan' WHERE kind = 'business_plan'")
    op.execute("UPDATE attachment SET kind = 'other' WHERE kind = 'howto_file'")
    op.create_check_constraint(op.f("ck_attachment_kind"), "attachment", f"kind IN ({_OLD_KINDS})")
    op.create_check_constraint(
        op.f("ck_attachment_size_limit"), "attachment", "size_bytes <= 10485760"
    )
