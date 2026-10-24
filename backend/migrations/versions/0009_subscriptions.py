"""Subscriptions: `interest`, `subscriber`, `subscription_profile`, `outbox`, lists, digests.

Revision ID: 0009_subscriptions
Revises: 0008_public_site
Create Date: 2026-10-24 00:00:09

Adds the tables of the mail and profile subscriptions (B3-KONTRAKT 2.1) and the five
`privacy_*` functions (2.4), the only way to remove personal data. The functions are
`SECURITY DEFINER` and return counts, never rows. The address lives only as `pgcrypto`
ciphertext plus a keyed hash. No table holds an IP address or a user agent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from app.modules.subscriptions.interest_seed import seed_rows

revision: str = "0009_subscriptions"
down_revision: str | None = "0008_public_site"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = """
CREATE TABLE interest (
    slug text PRIMARY KEY,
    label text NOT NULL,
    category_ids uuid[] NOT NULL,
    sort integer NOT NULL,
    active boolean NOT NULL DEFAULT true,
    CONSTRAINT ck_interest_slug_ok CHECK (slug ~ '^[a-z][a-z0-9-]{1,39}$')
);

CREATE TABLE subscriber (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email_enc bytea,
    email_hmac text,
    status text NOT NULL,
    confirm_token_hash text,
    confirm_expires_at timestamptz,
    manage_token_hash text,
    manage_expires_at timestamptz,
    consent_text_version text NOT NULL,
    consent_categories text[] NOT NULL DEFAULT '{}',
    consent_at timestamptz NOT NULL,
    confirmed_at timestamptz,
    unsubscribed_at timestamptz,
    listmonk_subscriber_id integer,
    mails_day date NOT NULL DEFAULT current_date,
    mails_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_subscriber_email_hmac UNIQUE (email_hmac),
    CONSTRAINT ck_subscriber_status_ok
        CHECK (status IN ('pending', 'confirmed', 'unsubscribed', 'bounced', 'erased')),
    CONSTRAINT ck_subscriber_address_present
        CHECK (status = 'erased' OR (email_enc IS NOT NULL AND email_hmac IS NOT NULL)),
    CONSTRAINT ck_subscriber_mails_count_ok CHECK (mails_count >= 0)
);

CREATE INDEX ix_subscriber_status_created ON subscriber (status, created_at);

CREATE UNIQUE INDEX uq_subscriber_confirm_token ON subscriber (confirm_token_hash)
    WHERE confirm_token_hash IS NOT NULL;

CREATE UNIQUE INDEX uq_subscriber_manage_token ON subscriber (manage_token_hash)
    WHERE manage_token_hash IS NOT NULL;

CREATE TABLE subscription_profile (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id uuid REFERENCES subscriber (id) ON DELETE SET NULL,
    questionnaire_version integer NOT NULL,
    interests jsonb NOT NULL,
    categories text[] NOT NULL,
    ics_token_hash text NOT NULL,
    ics_token_rotated_at timestamptz NOT NULL DEFAULT now(),
    mail_enabled boolean NOT NULL DEFAULT false,
    last_fetched_on date,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_subscription_profile_ics_token_hash UNIQUE (ics_token_hash),
    CONSTRAINT uq_subscription_profile_subscriber_id UNIQUE (subscriber_id),
    CONSTRAINT ck_subscription_profile_categories_max CHECK (cardinality(categories) <= 40)
);

CREATE TABLE outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    op text NOT NULL,
    subscriber_id uuid REFERENCES subscriber (id) ON DELETE SET NULL,
    idempotency_key text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}',
    state text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    next_at timestamptz NOT NULL DEFAULT now(),
    locked_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    done_at timestamptz,
    CONSTRAINT uq_outbox_idempotency_key UNIQUE (idempotency_key),
    CONSTRAINT ck_outbox_op_ok CHECK (op IN ('upsert', 'unsubscribe', 'delete', 'ensure_list')),
    CONSTRAINT ck_outbox_state_ok CHECK (state IN ('pending', 'running', 'done', 'dead'))
);

CREATE INDEX ix_outbox_due ON outbox (next_at) WHERE state = 'pending';

CREATE TABLE listmonk_list (
    key text PRIMARY KEY,
    listmonk_id integer NOT NULL,
    name text NOT NULL,
    archived_at timestamptz
);

CREATE TABLE digest_run (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start date NOT NULL,
    list_key text NOT NULL,
    campaign_id integer,
    status text NOT NULL,
    event_count integer NOT NULL,
    released_by_sub text,
    released_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_digest_run_week_start UNIQUE (week_start, list_key),
    CONSTRAINT ck_digest_run_status_ok CHECK (status IN ('draft', 'released', 'skipped'))
);
"""

_ERASE = """
CREATE FUNCTION privacy_erase_subscriber(p_id uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE s subscriber%ROWTYPE;
BEGIN
    SELECT * INTO s FROM subscriber WHERE id = p_id FOR UPDATE;
    IF NOT FOUND OR s.status = 'erased' THEN
        RETURN 0;
    END IF;
    IF s.status <> 'pending' THEN
        INSERT INTO outbox (op, subscriber_id, idempotency_key, payload)
        VALUES ('delete', p_id, 'delete:' || p_id || '\\:0',
                jsonb_build_object('listmonkSubscriberId', s.listmonk_subscriber_id,
                                   'emailEnc', encode(s.email_enc, 'base64')))
        ON CONFLICT (idempotency_key) DO NOTHING;
    END IF;
    UPDATE outbox SET state = 'done', done_at = now()
    WHERE subscriber_id = p_id AND op <> 'delete' AND state IN ('pending', 'running');
    DELETE FROM subscription_profile WHERE subscriber_id = p_id;
    UPDATE subscriber SET
        status = 'erased', email_enc = NULL, email_hmac = NULL,
        confirm_token_hash = NULL, confirm_expires_at = NULL,
        manage_token_hash = NULL, manage_expires_at = NULL,
        consent_categories = '{}', listmonk_subscriber_id = NULL,
        unsubscribed_at = coalesce(unsubscribed_at, now()), updated_at = now()
    WHERE id = p_id;
    RETURN 1;
END $$;
"""

_PURGE_PENDING = """
CREATE FUNCTION privacy_purge_pending(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    UPDATE subscription_profile SET mail_enabled = false, updated_at = now()
    WHERE subscriber_id IN (
        SELECT id FROM subscriber WHERE status = 'pending' AND created_at < p_cutoff);
    DELETE FROM subscriber WHERE status = 'pending' AND created_at < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
"""

_ANONYMIZE = """
CREATE FUNCTION privacy_anonymize_unsubscribed(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer := 0; r uuid;
BEGIN
    FOR r IN SELECT id FROM subscriber
             WHERE status IN ('unsubscribed', 'bounced')
               AND coalesce(unsubscribed_at, updated_at) < p_cutoff LOOP
        n := n + privacy_erase_subscriber(r);
    END LOOP;
    RETURN n;
END $$;
"""

_PURGE_PROFILES = """
CREATE FUNCTION privacy_purge_profiles(p_cutoff date) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    DELETE FROM subscription_profile
    WHERE subscriber_id IS NULL AND coalesce(last_fetched_on, created_at::date) < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
"""

_PURGE_OUTBOX = """
CREATE FUNCTION privacy_purge_outbox(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    DELETE FROM outbox WHERE state = 'done' AND done_at < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
"""

_FUNCTIONS = (
    "privacy_erase_subscriber(uuid)",
    "privacy_purge_pending(timestamptz)",
    "privacy_anonymize_unsubscribed(timestamptz)",
    "privacy_purge_profiles(date)",
    "privacy_purge_outbox(timestamptz)",
)
_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_subs') THEN
        GRANT SELECT, INSERT, UPDATE
            ON subscriber, subscription_profile, outbox, listmonk_list, digest_run
            TO events_subs;
        GRANT SELECT ON interest, public_event_v, public_category_v TO events_subs;
        GRANT EXECUTE ON FUNCTION {functions} TO events_subs;
    END IF;
END $$;
""".replace("{functions}", ", ".join(_FUNCTIONS))

_INTEREST = sa.table(
    "interest",
    sa.column("slug", sa.Text),
    sa.column("label", sa.Text),
    sa.column("category_ids", pg.ARRAY(pg.UUID(as_uuid=True))),
    sa.column("sort", sa.Integer),
)


def upgrade() -> None:
    for statement in _TABLES.split(";\n\n"):
        op.execute(statement)
    op.bulk_insert(_INTEREST, seed_rows())
    for ddl in (_ERASE, _PURGE_PENDING, _ANONYMIZE, _PURGE_PROFILES, _PURGE_OUTBOX):
        op.execute(ddl)
    for signature in _FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(_GRANTS)


def downgrade() -> None:
    for signature in reversed(_FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
    for table in ("digest_run", "listmonk_list", "outbox", "subscription_profile", "subscriber"):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TABLE interest")
