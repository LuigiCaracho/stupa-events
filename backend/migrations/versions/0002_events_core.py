"""Events core: organizations, categories, events, attachments, publish triggers, public view.

Revision ID: 0002_events_core
Revises: 0001_baseline
Create Date: 2026-10-18 00:00:02

A real revision, no `create_all`. It creates `organization`, `group_mapping`, `category`,
`event`, `event_revision`, `event_status_event` and `attachment`, the trigger
`enforce_publish_image` (a state `approved` or `live` needs a valid poster or a valid
image exception, for INSERT and UPDATE), the trigger that stops a poster of a published
event from getting worse, the append-only triggers, the view `public_event_v` and the
conditional grants for the roles `events_app` and `events_public`. The reference rows
(organizations, categories) come from `app.modules.taxonomy.reference`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.modules.events.models import CONTROL_CHARS
from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS

revision: str = "0002_events_core"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATES = "'idea','planning','in_review','approved','live','followup','archived','withdrawn'"
_ROLES = "'viewer','submitter','organizer','approver','admin','editor','stupa','member'"
_GLOBAL_ROLES = "'admin','editor','stupa','member'"

_POSTER_FUNCTIONS = """
CREATE FUNCTION exception_ok(j jsonb) RETURNS boolean
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT j IS NOT NULL AND length(btrim(coalesce(j ->> 'reason', ''))) >= 10 $$;
-- split
CREATE FUNCTION attachment_poster_ok(a attachment) RETURNS boolean
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT a.kind = 'poster'
        AND a.scan_status = 'clean'
        AND a.retired_at IS NULL
        AND coalesce(a.alt_text, '') <> ''
        AND coalesce(a.credit, '') <> ''
        AND a.rights_basis <> 'unknown'
        AND a.derivatives IS NOT NULL
        AND a.derivatives ?& ARRAY['thumb_400', 'card_1200', 'og_1200x630'] $$;
"""

_PUBLISH_TRIGGER = """
CREATE FUNCTION enforce_publish_image() RETURNS trigger AS $$
BEGIN
    IF NEW.state IN ('approved', 'live') AND NOT (
        exception_ok(NEW.image_exception)
        OR EXISTS (
            SELECT 1 FROM attachment a
            WHERE a.id = NEW.hero_attachment_id AND a.event_id = NEW.id
              AND attachment_poster_ok(a)
        )
    ) THEN
        RAISE EXCEPTION 'event % cannot be % without a valid poster or image exception',
            NEW.id, NEW.state
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- split
CREATE TRIGGER trg_event_enforce_publish_image
    BEFORE INSERT OR UPDATE OF state, hero_attachment_id, image_exception ON event
    FOR EACH ROW EXECUTE FUNCTION enforce_publish_image();
"""

_POSTER_GUARD_TRIGGER = """
CREATE FUNCTION keep_published_poster() RETURNS trigger AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM event e
        WHERE e.hero_attachment_id = OLD.id
          AND e.state IN ('approved', 'live')
          AND NOT exception_ok(e.image_exception)
    ) AND NOT attachment_poster_ok(NEW) THEN
        RAISE EXCEPTION 'attachment % is the poster of a published event', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- split
CREATE TRIGGER trg_attachment_keep_published_poster
    BEFORE UPDATE ON attachment
    FOR EACH ROW EXECUTE FUNCTION keep_published_poster();
"""

_APPEND_ONLY = """
CREATE FUNCTION append_only_guard() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; % denied', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""

_PUBLIC_VIEW = """
CREATE VIEW public_event_v AS
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
       e.venue_text,
       c.slug AS category_slug,
       c.name AS category_name,
       c.kind AS category_kind,
       a.sha256 AS hero_sha,
       a.derivatives AS hero_derivatives,
       a.alt_text AS hero_alt,
       a.credit AS hero_credit,
       e.updated_at
FROM event e
JOIN organization o ON o.id = e.organization_id
LEFT JOIN category c ON c.id = e.primary_category_id
LEFT JOIN attachment a ON a.id = e.hero_attachment_id AND a.event_id = e.id
    AND attachment_poster_ok(a)
WHERE e.state IN ('live', 'followup', 'archived')
  AND e.slug IS NOT NULL
  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))
"""

_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON event_revision, event_status_event FROM events_app;
        REVOKE DELETE, TRUNCATE ON event, attachment, organization, category, group_mapping
            FROM events_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        REVOKE ALL ON event, attachment, organization, category, group_mapping, event_revision,
            event_status_event, principal, auth_session, audit_entry FROM events_public;
        GRANT SELECT ON public_event_v TO events_public;
    END IF;
END $$;
"""


def _execute(script: str) -> None:
    """Run a script statement by statement (asyncpg takes one command per call)."""
    for statement in script.split("\n-- split\n"):
        op.execute(statement)


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _in(column: str, values: str) -> str:
    return f"{column} IN ({values})"


def _create_taxonomy() -> None:
    op.create_table(
        "category",
        _uuid_pk(),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid,
            sa.ForeignKey(
                "category.id", ondelete="RESTRICT", name="fk_category_parent_id_category"
            ),
        ),
        sa.Column("short", sa.Text),
        sa.Column("color_token", sa.Text),
        sa.Column("required_profile", sa.Text, server_default="generic", nullable=False),
        sa.Column("legacy_wp_id", sa.Integer),
        sa.Column("sort", sa.Integer, server_default="0", nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_category_slug"),
        sa.CheckConstraint("kind IN ('format', 'fachschaft', 'partner')", name="ck_category_kind"),
        sa.CheckConstraint(
            "required_profile IN ('generic', 'party', 'meeting', 'trip')",
            name="ck_category_required_profile",
        ),
    )
    op.create_table(
        "organization",
        _uuid_pk(),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column(
            "parent_id",
            sa.Uuid,
            sa.ForeignKey(
                "organization.id",
                ondelete="RESTRICT",
                name="fk_organization_parent_id_organization",
            ),
        ),
        sa.Column("short", sa.Text, nullable=False),
        sa.Column("color_token", sa.Text),
        sa.Column(
            "category_id",
            sa.Uuid,
            sa.ForeignKey(
                "category.id", ondelete="RESTRICT", name="fk_organization_category_id_category"
            ),
        ),
        sa.Column("contact_public", pg.JSONB),
        sa.Column("trusted", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("instagram", pg.ARRAY(sa.Text), server_default="{}", nullable=False),
        sa.Column("legacy_wp_ids", pg.ARRAY(sa.Integer), server_default="{}", nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_organization_slug"),
        sa.CheckConstraint(
            "kind IN ('stupa','referat','fachschaft','partner','hochschule','redaktion')",
            name="ck_organization_kind",
        ),
    )
    op.create_table(
        "group_mapping",
        _uuid_pk(),
        sa.Column("oidc_group", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey(
                "organization.id",
                ondelete="CASCADE",
                name="fk_group_mapping_organization_id_organization",
            ),
        ),
        *_timestamps(),
        sa.UniqueConstraint("oidc_group", name="uq_group_mapping_oidc_group"),
        sa.CheckConstraint(_in("role", _ROLES), name="ck_group_mapping_role"),
        sa.CheckConstraint(
            f"(organization_id IS NULL) = (role IN ({_GLOBAL_ROLES}))",
            name="ck_group_mapping_scope",
        ),
        sa.CheckConstraint(
            "oidc_group NOT LIKE 'events-system:%'", name="ck_group_mapping_reserved_namespace"
        ),
    )


def _create_attachment() -> None:
    op.create_table(
        "attachment",
        _uuid_pk(),
        sa.Column("event_id", sa.Uuid, nullable=False),
        sa.Column("kind", sa.Text, server_default="poster", nullable=False),
        sa.Column("storage_key", sa.Text),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("storage_name", sa.Text, nullable=False),
        sa.Column("mime", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("scan_status", sa.Text, server_default="pending", nullable=False),
        sa.Column("scan_result", sa.Text),
        sa.Column("alt_text", sa.Text),
        sa.Column("credit", sa.Text),
        sa.Column("rights_basis", sa.Text, server_default="unknown", nullable=False),
        sa.Column("license_ref", sa.Text),
        sa.Column("source_url", sa.Text),
        sa.Column("persons_depicted", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("consent_note", sa.Text),
        sa.Column("visibility", sa.Text, server_default="org", nullable=False),
        sa.Column("meta", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("derivatives", pg.JSONB),
        sa.Column(
            "supersedes_id",
            sa.Uuid,
            sa.ForeignKey(
                "attachment.id", ondelete="RESTRICT", name="fk_attachment_supersedes_id_attachment"
            ),
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("size_bytes <= 10485760", name="ck_attachment_size_limit"),
        sa.CheckConstraint(
            "kind IN ('poster','social_post','poster_print','businessplan','quote','contract',"
            "'mail_attachment','other')",
            name="ck_attachment_kind",
        ),
        sa.CheckConstraint(
            "scan_status IN ('pending','clean','infected','error')",
            name="ck_attachment_scan_status",
        ),
        sa.CheckConstraint(
            "rights_basis IN ('own_work','permission','license','partner_agreement','unknown')",
            name="ck_attachment_rights_basis",
        ),
        sa.CheckConstraint(
            "visibility IN ('team','org','shared')", name="ck_attachment_visibility"
        ),
    )
    op.create_index("ix_attachment_event_id", "attachment", ["event_id"])


def _create_event() -> None:
    op.create_table(
        "event",
        _uuid_pk(),
        sa.Column("slug", sa.Text),
        sa.Column("state", sa.Text, server_default="idea", nullable=False),
        sa.Column("public_status", sa.Text, server_default="scheduled", nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("description_md", sa.Text),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tzid", sa.Text, server_default="Europe/Berlin", nullable=False),
        sa.Column("all_day", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("starts_on", sa.Date),
        sa.Column("ends_on", sa.Date),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey(
                "organization.id", ondelete="RESTRICT", name="fk_event_organization_id_organization"
            ),
        ),
        sa.Column("venue_text", sa.Text),
        sa.Column(
            "primary_category_id",
            sa.Uuid,
            sa.ForeignKey(
                "category.id", ondelete="RESTRICT", name="fk_event_primary_category_id_category"
            ),
        ),
        sa.Column("hero_attachment_id", sa.Uuid),
        sa.Column("image_exception", pg.JSONB),
        sa.Column("origin_kind", sa.Text, server_default="internal", nullable=False),
        sa.Column("rev", sa.Integer, server_default="1", nullable=False),
        sa.Column("public_seq", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("submitted_by", sa.Text),
        sa.Column("approved_by", sa.Text),
        *_timestamps(),
        sa.CheckConstraint(_in("state", _STATES), name="ck_event_state"),
        sa.CheckConstraint(
            "public_status IN ('scheduled','cancelled','postponed')", name="ck_event_public_status"
        ),
        sa.CheckConstraint(
            "origin_kind IN ('internal','imported','legacy','mcp')", name="ck_event_origin_kind"
        ),
        sa.CheckConstraint("ends_at >= starts_at", name="ck_event_time_order"),
        sa.CheckConstraint("all_day = (starts_on IS NOT NULL)", name="ck_event_all_day_days"),
        sa.CheckConstraint(
            "state IN ('idea', 'withdrawn') OR organization_id IS NOT NULL",
            name="ck_event_organization",
        ),
        sa.CheckConstraint(f"title !~ '{CONTROL_CHARS}'", name="ck_event_title_clean"),
        sa.CheckConstraint(f"summary !~ '{CONTROL_CHARS}'", name="ck_event_summary_clean"),
        sa.CheckConstraint(f"venue_text !~ '{CONTROL_CHARS}'", name="ck_event_venue_text_clean"),
        sa.CheckConstraint("rev >= 1", name="ck_event_rev"),
    )
    op.create_foreign_key(
        "fk_event_hero_attachment_id_attachment",
        "event",
        "attachment",
        ["hero_attachment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_attachment_event_id_event",
        "attachment",
        "event",
        ["event_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_event_slug",
        "event",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )
    op.create_index("ix_event_organization_id_starts_at", "event", ["organization_id", "starts_at"])
    op.create_index("ix_event_state", "event", ["state"])


def _create_history() -> None:
    op.create_table(
        "event_revision",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Uuid,
            sa.ForeignKey("event.id", ondelete="RESTRICT", name="fk_event_revision_event_id_event"),
            nullable=False,
        ),
        sa.Column("rev", sa.Integer, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_id", sa.Text),
        sa.Column("actor_type", sa.Text, server_default="human", nullable=False),
        sa.Column("change_note", sa.Text),
        sa.Column("field_class", sa.Text, nullable=False),
        sa.Column("snapshot", pg.JSONB, nullable=False),
        sa.UniqueConstraint("event_id", "rev", name="uq_event_revision_event_id_rev"),
        sa.CheckConstraint(
            "actor_type IN ('human','agent','system')", name="ck_event_revision_actor_type"
        ),
        sa.CheckConstraint(
            "field_class IN ('critical','text','dossier','state')",
            name="ck_event_revision_field_class",
        ),
    )
    op.create_table(
        "event_status_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Uuid,
            sa.ForeignKey(
                "event.id", ondelete="RESTRICT", name="fk_event_status_event_event_id_event"
            ),
            nullable=False,
        ),
        sa.Column("from_state", sa.Text),
        sa.Column("to_state", sa.Text, nullable=False),
        sa.Column("transition_id", sa.Text, nullable=False),
        sa.Column("actor_id", sa.Text),
        sa.Column("actor_type", sa.Text, server_default="human", nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(_in("to_state", _STATES), name="ck_event_status_event_to_state"),
        sa.CheckConstraint(
            "actor_type IN ('human','agent','system')", name="ck_event_status_event_actor_type"
        ),
        sa.CheckConstraint(
            "note IS NULL OR length(note) <= 500", name="ck_event_status_event_note_length"
        ),
    )
    op.create_index("ix_event_status_event_event_id", "event_status_event", ["event_id"])


def _seed() -> None:
    category = sa.table(
        "category",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.Text),
        sa.column("name", sa.Text),
        sa.column("kind", sa.Text),
        sa.column("parent_id", sa.Uuid),
        sa.column("short", sa.Text),
        sa.column("color_token", sa.Text),
        sa.column("required_profile", sa.Text),
        sa.column("legacy_wp_id", sa.Integer),
    )
    organization = sa.table(
        "organization",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.Text),
        sa.column("name", sa.Text),
        sa.column("kind", sa.Text),
        sa.column("short", sa.Text),
        sa.column("category_id", sa.Uuid),
        sa.column("color_token", sa.Text),
        sa.column("legacy_wp_ids", pg.ARRAY(sa.Integer)),
        sa.column("trusted", sa.Boolean),
    )
    parents_first = sorted(CATEGORIES, key=lambda row: row["parent_id"] is not None)
    op.bulk_insert(category, [dict(row) for row in parents_first])
    op.bulk_insert(organization, [dict(row) for row in ORGANIZATIONS])


def upgrade() -> None:
    _create_taxonomy()
    _create_attachment()
    _create_event()
    _create_history()

    _execute(_POSTER_FUNCTIONS)
    _execute(_PUBLISH_TRIGGER)
    _execute(_POSTER_GUARD_TRIGGER)
    op.execute(_APPEND_ONLY)
    for table in ("event_revision", "event_status_event"):
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION append_only_guard()"
            )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION append_only_guard()"
        )
    op.execute(_PUBLIC_VIEW)
    op.execute(_GRANTS)
    _seed()


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS public_event_v")
    for table in ("event_status_event", "event_revision", "event", "attachment"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for table in ("group_mapping", "organization", "category"):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for function in (
        "enforce_publish_image()",
        "keep_published_poster()",
        "append_only_guard()",
        "attachment_poster_ok(attachment)",
        "exception_ok(jsonb)",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function} CASCADE")
