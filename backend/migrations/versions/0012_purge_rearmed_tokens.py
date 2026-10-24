"""Pending purge also clears the unconfirmed re-arm of an unsubscribed or bounced address.

Revision ID: 0012_purge_rearmed
Revises: 0011_erase_blocklist
Create Date: 2026-10-25 00:00:12

A repeat sign-up of an unsubscribed or bounced address keeps the old status and only sets a new
confirm token. The 48 hour rule must apply to that token too, so `privacy_purge_pending` clears
token and expiry of such rows once they have expired.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_purge_rearmed"
down_revision: str | None = "0011_erase_blocklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = """
CREATE OR REPLACE FUNCTION privacy_purge_pending(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer; m integer;
BEGIN
    UPDATE subscription_profile SET mail_enabled = false, updated_at = now()
    WHERE subscriber_id IN (
        SELECT id FROM subscriber WHERE status = 'pending' AND created_at < p_cutoff);
    DELETE FROM subscriber WHERE status = 'pending' AND created_at < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    UPDATE subscriber SET confirm_token_hash = NULL, confirm_expires_at = NULL, updated_at = now()
    WHERE status IN ('unsubscribed', 'bounced') AND confirm_token_hash IS NOT NULL
      AND confirm_expires_at < now();
    GET DIAGNOSTICS m = ROW_COUNT;
    RETURN n + m;
END $$;
"""

_OLD = """
CREATE OR REPLACE FUNCTION privacy_purge_pending(p_cutoff timestamptz) RETURNS integer
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


def upgrade() -> None:
    op.execute(_NEW)


def downgrade() -> None:
    op.execute(_OLD)
