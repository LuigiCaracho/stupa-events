"""Retention of `dead` outbox jobs: the purge strips their ciphertext after the same cutoff.

Revision ID: 0010_purge_dead_pii
Revises: 0009_subscriptions
Create Date: 2026-10-25 00:00:10

A `delete` or `unsubscribe` job keeps the pgcrypto ciphertext of the address in its payload until
it succeeds. A job that ends `dead` kept it for good; now `privacy_purge_outbox` removes the
ciphertext from dead jobs older than the cutoff as well (the row stays as the alarm record).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_purge_dead_pii"
down_revision: str | None = "0009_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = """
CREATE OR REPLACE FUNCTION privacy_purge_outbox(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer; m integer;
BEGIN
    DELETE FROM outbox WHERE state = 'done' AND done_at < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    UPDATE outbox SET payload = payload - 'emailEnc'
    WHERE state = 'dead' AND op IN ('delete', 'unsubscribe')
      AND payload ? 'emailEnc' AND created_at < p_cutoff;
    GET DIAGNOSTICS m = ROW_COUNT;
    RETURN n + m;
END $$;
"""

_OLD = """
CREATE OR REPLACE FUNCTION privacy_purge_outbox(p_cutoff timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    DELETE FROM outbox WHERE state = 'done' AND done_at < p_cutoff;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END $$;
"""


def upgrade() -> None:
    op.execute(_NEW)


def downgrade() -> None:
    op.execute(_OLD)
