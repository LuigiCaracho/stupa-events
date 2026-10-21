"""Event dossier: three states, no approval pipeline, optional poster, no `approver`.

Revision ID: 0007_event_dossier
Revises: 0006_archive_feed
Create Date: 2026-10-21 00:00:07

Maps the eight pipeline states onto `draft`, `published` and `archived` (one
`event_status_event` row per changed event), folds the role `approver` into `organizer`,
drops the notification kinds of the pipeline, tightens `state`, `organization` and `tzid`,
rebuilds `public_event_v` without the image exception, softens `attachment_poster_ok` (alt
text, credit and rights basis become hints) and removes the publish triggers, the Four-Eyes
and field class columns, the review markers, `publish_at` and `organization.trusted`.
`event_status_event` and `event_revision` are append-only, so the old state names stay in the
history and the CHECK on `to_state` accepts both vocabularies.

The migration is one-way for data: the downgrade rebuilds the old structure (columns as
nullable, `live` for `published`, `idea` for `draft`) but restores no value.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_event_dossier"
down_revision: str | None = "0006_archive_feed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")

_OLD_STATES = "'idea','planning','in_review','approved','live','followup','archived','withdrawn'"
_NEW_STATES = "'draft','published','archived'"
_ALL_STATES = "'draft','published'," + _OLD_STATES
_STATE_MAP = {
    "idea": "draft",
    "planning": "draft",
    "in_review": "draft",
    "withdrawn": "draft",
    "approved": "draft",
    "live": "published",
    "followup": "archived",
    "archived": "archived",
}
_NEW_STATE_CASE = (
    "CASE state "
    + " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in _STATE_MAP.items())
    + " END"
)
_OLD_ROLES = "'viewer','submitter','organizer','approver'"
_NEW_ROLES = "'viewer','submitter','organizer'"
_OLD_MAPPING_ROLES = "'viewer','submitter','organizer','approver','admin','editor','stupa','member'"
_NEW_MAPPING_ROLES = "'viewer','submitter','organizer','admin','editor','stupa','member'"
_OLD_KINDS = (
    "'review_requested','changes_requested','comment_added','comment_resolved',"
    "'transition_done','task_assigned','checklist_due','followup_reminder','auto_archived'"
)
_NEW_KINDS = "'comment_added','published','cancelled','checklist_due'"
_REMOVED_EVENT_COLUMNS = (
    "submitted_by",
    "approved_by",
    "image_exception",
    "publish_at",
    "published_rev",
    "text_reviewed_rev",
    "flyer_checked_at",
)

_POSTER_OK = """
CREATE OR REPLACE FUNCTION attachment_poster_ok(a attachment) RETURNS boolean
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT a.kind = 'poster'
        AND a.scan_status = 'clean'
        AND a.retired_at IS NULL
        AND (NOT a.persons_depicted OR btrim(coalesce(a.consent_note, '')) <> '')
        AND a.derivatives IS NOT NULL
        AND a.derivatives ?& ARRAY['thumb_400', 'card_1200', 'og_1200x630'] $$
"""

_POSTER_OK_OLD = """
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

_VIEW_BODY = """
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
"""

_VIEW_NEW = (
    "CREATE OR REPLACE VIEW public_event_v AS"
    + _VIEW_BODY
    + "WHERE e.state IN ('published', 'archived') AND e.slug IS NOT NULL"
)
_VIEW_OLD = (
    "CREATE OR REPLACE VIEW public_event_v AS"
    + _VIEW_BODY
    + "WHERE e.state IN ('live', 'followup', 'archived') AND e.slug IS NOT NULL\n"
    "  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))"
)

_OLD_FUNCTIONS = """
CREATE FUNCTION exception_ok(j jsonb) RETURNS boolean
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT j IS NOT NULL AND length(btrim(coalesce(j ->> 'reason', ''))) >= 10 $$;
-- split
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
-- split
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
    FOR EACH ROW EXECUTE FUNCTION keep_published_poster()
"""

_DROP_OLD_FUNCTIONS = (
    "DROP TRIGGER IF EXISTS trg_event_enforce_publish_image ON event",
    "DROP TRIGGER IF EXISTS trg_attachment_keep_published_poster ON attachment",
    "DROP FUNCTION IF EXISTS enforce_publish_image()",
    "DROP FUNCTION IF EXISTS keep_published_poster()",
    "DROP FUNCTION IF EXISTS exception_ok(jsonb)",
)


def _swap_check(table: str, old: str, new: str, expression: str | None) -> None:
    op.drop_constraint(old, table)
    if expression is not None:
        op.create_check_constraint(op.f(new), table, expression)


def _migrate_states() -> None:
    bind = op.get_bind()
    held = bind.execute(
        sa.text("SELECT count(*) FROM event WHERE state = 'approved' AND publish_at <= now()")
    ).scalar_one()
    log.info("0007: %s approved events with an elapsed publish_at become drafts", held)
    bind.execute(
        sa.text(
            "INSERT INTO event_status_event "
            "(event_id, from_state, to_state, transition_id, actor_id, actor_type, note) "
            f"SELECT id, state, {_NEW_STATE_CASE}, 'migration-0007', 'system:migration-0007', "
            "'system', 'Zustandsmodell vereinfacht' "
            f"FROM event WHERE state <> {_NEW_STATE_CASE}"
        )
    )
    bind.execute(sa.text(f"UPDATE event SET state = {_NEW_STATE_CASE}"))


def _migrate_roles() -> None:
    op.execute(
        "DELETE FROM membership m WHERE m.role = 'approver' AND EXISTS ("
        "SELECT 1 FROM membership o WHERE o.principal_id = m.principal_id "
        "AND o.organization_id = m.organization_id AND o.role = 'organizer')"
    )
    op.execute("UPDATE membership SET role = 'organizer' WHERE role = 'approver'")
    op.execute("UPDATE group_mapping SET role = 'organizer' WHERE role = 'approver'")
    _swap_check(
        "membership",
        "ck_membership_ck_membership_role",
        op.f("ck_membership_role"),
        f"role IN ({_NEW_ROLES})",
    )
    _swap_check(
        "group_mapping",
        "ck_group_mapping_ck_group_mapping_role",
        op.f("ck_group_mapping_role"),
        f"role IN ({_NEW_MAPPING_ROLES})",
    )


def _migrate_notifications() -> None:
    for table in ("notification_pref", "notification"):
        op.execute(f"DELETE FROM {table} WHERE kind NOT IN ({_NEW_KINDS})")
    for table in ("notification", "notification_pref"):
        _swap_check(
            table, op.f(f"ck_{table}_kind"), op.f(f"ck_{table}_kind"), f"kind IN ({_NEW_KINDS})"
        )


def _drop_pipeline_objects() -> None:
    for statement in _DROP_OLD_FUNCTIONS:
        op.execute(statement)
    op.drop_constraint(op.f("ck_event_status_event_four_eyes"), "event_status_event")
    op.drop_column("event_status_event", "submitted_by")
    op.drop_column("event_status_event", "four_eyes")
    op.drop_constraint("ck_event_revision_ck_event_revision_field_class", "event_revision")
    op.drop_column("event_revision", "field_class")
    for column in _REMOVED_EVENT_COLUMNS:
        op.drop_column("event", column)
    op.drop_column("organization", "trusted")


def upgrade() -> None:
    op.drop_constraint("ck_event_status_event_ck_event_status_event_to_state", "event_status_event")
    op.create_check_constraint(
        op.f("ck_event_status_event_to_state"), "event_status_event", f"to_state IN ({_ALL_STATES})"
    )
    op.drop_constraint("ck_event_ck_event_state", "event")
    op.drop_constraint("ck_event_ck_event_organization", "event")
    _migrate_states()
    op.create_check_constraint(op.f("ck_event_state"), "event", f"state IN ({_NEW_STATES})")
    op.create_check_constraint(
        op.f("ck_event_organization"), "event", "state = 'draft' OR organization_id IS NOT NULL"
    )
    op.execute("UPDATE event SET tzid = 'Europe/Berlin' WHERE tzid <> 'Europe/Berlin'")
    op.create_check_constraint(op.f("ck_event_tzid"), "event", "tzid = 'Europe/Berlin'")
    _migrate_roles()
    _migrate_notifications()
    op.execute(_POSTER_OK)
    op.execute(_VIEW_NEW)
    _drop_pipeline_objects()


def _restore_pipeline_objects() -> None:
    op.add_column(
        "organization",
        sa.Column("trusted", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )
    op.add_column("event", sa.Column("submitted_by", sa.Text))
    op.add_column("event", sa.Column("approved_by", sa.Text))
    op.add_column("event", sa.Column("image_exception", sa.dialects.postgresql.JSONB))
    op.add_column("event", sa.Column("publish_at", sa.DateTime(timezone=True)))
    op.add_column("event", sa.Column("published_rev", sa.Integer))
    op.add_column(
        "event", sa.Column("text_reviewed_rev", sa.Integer, server_default="0", nullable=False)
    )
    op.add_column("event", sa.Column("flyer_checked_at", sa.DateTime(timezone=True)))
    op.add_column(
        "event_revision",
        sa.Column("field_class", sa.Text, server_default="state", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_event_revision_ck_event_revision_field_class"),
        "event_revision",
        "field_class IN ('critical','text','dossier','state')",
    )
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
    for statement in _OLD_FUNCTIONS.split("-- split"):
        op.execute(statement)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_event_tzid"), "event")
    op.drop_constraint(op.f("ck_event_organization"), "event")
    op.drop_constraint(op.f("ck_event_state"), "event")
    op.execute(
        "UPDATE event SET state = CASE state WHEN 'published' THEN 'live' ELSE 'idea' END "
        "WHERE state IN ('published', 'draft')"
    )
    op.create_check_constraint(
        op.f("ck_event_ck_event_state"), "event", f"state IN ({_OLD_STATES})"
    )
    op.create_check_constraint(
        op.f("ck_event_ck_event_organization"),
        "event",
        "state IN ('idea', 'withdrawn') OR organization_id IS NOT NULL",
    )
    op.drop_constraint(op.f("ck_event_status_event_to_state"), "event_status_event")
    op.create_check_constraint(
        op.f("ck_event_status_event_ck_event_status_event_to_state"),
        "event_status_event",
        f"to_state IN ({_ALL_STATES})",
    )
    _restore_pipeline_objects()
    op.execute(_POSTER_OK_OLD)
    op.execute(_VIEW_OLD)
    for table in ("notification", "notification_pref"):
        name = op.f(f"ck_{table}_kind")
        _swap_check(table, name, name, f"kind IN ({_OLD_KINDS})")
    _swap_check(
        "group_mapping",
        op.f("ck_group_mapping_role"),
        "ck_group_mapping_ck_group_mapping_role",
        f"role IN ({_OLD_MAPPING_ROLES})",
    )
    _swap_check(
        "membership",
        op.f("ck_membership_role"),
        "ck_membership_ck_membership_role",
        f"role IN ({_OLD_ROLES})",
    )
