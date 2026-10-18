"""Baseline: extensions, German text search, identity, audit chain, files-free media.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-18 00:00:01

A real revision, no `create_all`. It creates the extensions, the `de_unaccent` text search
configuration with the `immutable_unaccent` wrapper, the tables `principal`,
`auth_session`, `audit_entry`, `audit_verification` and `markdown_image`, and the raw DDL
of the audit chain: the `BEFORE UPDATE/DELETE/TRUNCATE` triggers that make `audit_entry`
append-only and the least-privilege grant for the optional role `events_audit_writer`.
The event tables, the publish triggers and the public views come with
`0002_events_core`.

Copied from STUPA-Workflow@93c33d6 backend/migrations/versions/0001_baseline.py (audit DDL)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_WRITER_ROLE = "events_audit_writer"
_APP_ROLE = "events_app"

_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION audit_entry_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_entry is append-only; % denied', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""

_AUDIT_GRANT = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_AUDIT_WRITER_ROLE}') THEN
        REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_entry FROM {_AUDIT_WRITER_ROLE};
        GRANT INSERT, SELECT ON TABLE audit_entry TO {_AUDIT_WRITER_ROLE};
    END IF;
END $$;
"""

_SESSION_GRANT = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_APP_ROLE}') THEN
        GRANT DELETE ON TABLE auth_session TO {_APP_ROLE};
    END IF;
END $$;
"""

_UNACCENT_WRAPPER = """
CREATE OR REPLACE FUNCTION immutable_unaccent(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;
"""

_TEXT_SEARCH_CREATE = (
    "CREATE TEXT SEARCH CONFIGURATION public.de_unaccent (COPY = pg_catalog.german)"
)
_TEXT_SEARCH_MAPPING = """
ALTER TEXT SEARCH CONFIGURATION public.de_unaccent
    ALTER MAPPING FOR hword, hword_part, word
    WITH public.unaccent, german_stem
"""


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    for extension in ("pgcrypto", "citext", "btree_gist", "pg_trgm", "unaccent"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")
    op.execute(_UNACCENT_WRAPPER)
    op.execute(_TEXT_SEARCH_CREATE)
    op.execute(_TEXT_SEARCH_MAPPING)

    op.create_table(
        "principal",
        _uuid_pk(),
        sa.Column("sub", sa.Text, nullable=False),
        sa.Column("email", pg.CITEXT, nullable=True),
        sa.Column("display_name", sa.Text, nullable=True),
        sa.Column("oidc_groups", pg.JSONB, nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("bootstrap_admin", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.UniqueConstraint("sub", name="uq_principal_sub"),
    )
    op.create_table(
        "auth_session",
        _uuid_pk(),
        sa.Column("sid", sa.Text, nullable=False),
        sa.Column(
            "principal_id",
            sa.Uuid,
            sa.ForeignKey("principal.id", ondelete="CASCADE", name="fk_auth_session_principal"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("id_token", sa.Text, nullable=True),
        sa.Column("client", sa.Text, server_default="web", nullable=False),
        sa.Column(
            "revalidated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        _created_at(),
        sa.UniqueConstraint("sid", name="uq_auth_session_sid"),
        sa.CheckConstraint("client IN ('web', 'pwa')", name="ck_auth_session_client"),
    )
    op.create_index("ix_auth_session_principal_id", "auth_session", ["principal_id"])

    op.create_table(
        "audit_entry",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("actor", sa.Text, nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=True),
        sa.Column("target_id", sa.Text, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data", pg.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("prev_hash", sa.LargeBinary, nullable=True),
        sa.Column("hash", sa.LargeBinary, nullable=False),
    )
    op.create_index("ix_audit_entry_at", "audit_entry", ["at"])
    op.create_index(
        "ix_audit_entry_target_type_target_id", "audit_entry", ["target_type", "target_id"]
    )
    op.create_table(
        "audit_verification",
        _uuid_pk(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid", sa.Boolean, nullable=False),
        sa.Column("checked", sa.BigInteger, nullable=False),
        sa.Column("broken_at", sa.BigInteger, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("triggered_by", sa.Text, nullable=True),
        sa.CheckConstraint(
            "trigger IN ('cron','manual','restore')", name="ck_audit_verification_trigger"
        ),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ('prev_hash_mismatch','hash_mismatch')",
            name="ck_audit_verification_reason",
        ),
        sa.CheckConstraint("valid = (reason IS NULL)", name="ck_audit_verification_valid_reason"),
    )
    op.execute(
        "CREATE INDEX ix_audit_verification_started_at ON audit_verification (started_at DESC)"
    )

    op.create_table(
        "markdown_image",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("mime", sa.Text, nullable=False),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "mime IN ('image/png', 'image/jpeg', 'image/gif', 'image/webp')",
            name="ck_markdown_image_mime",
        ),
        sa.CheckConstraint("size >= 0", name="ck_markdown_image_size"),
        sa.CheckConstraint("width > 0 AND height > 0", name="ck_markdown_image_dimensions"),
    )

    op.execute(_TRIGGER_FN)
    op.execute(
        "CREATE TRIGGER trg_audit_entry_no_update BEFORE UPDATE ON audit_entry "
        "FOR EACH ROW EXECUTE FUNCTION audit_entry_append_only();"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_entry_no_delete BEFORE DELETE ON audit_entry "
        "FOR EACH ROW EXECUTE FUNCTION audit_entry_append_only();"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_entry_no_truncate BEFORE TRUNCATE ON audit_entry "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_entry_append_only();"
    )
    op.execute(_AUDIT_GRANT)
    op.execute(_SESSION_GRANT)


def downgrade() -> None:
    for table in (
        "markdown_image",
        "audit_verification",
        "audit_entry",
        "auth_session",
        "principal",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS audit_entry_append_only()")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS public.de_unaccent")
    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text)")
