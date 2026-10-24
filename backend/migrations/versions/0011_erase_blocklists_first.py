"""Erasure queues a blocklist job before the delete job.

Revision ID: 0011_erase_blocklist
Revises: 0010_purge_dead_pii
Create Date: 2026-10-25 00:00:11

`privacy_erase_subscriber` used to queue only `delete`; until the worker had run, the person stayed
on the Listmonk lists and a released digest would still mail them. It now queues `unsubscribe`
(blocklist, with the ciphertext in the payload because the row is wiped at once) and then `delete`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_erase_blocklist"
down_revision: str | None = "0010_purge_dead_pii"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = """
CREATE OR REPLACE FUNCTION privacy_erase_subscriber(p_id uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE s subscriber%ROWTYPE;
BEGIN
    SELECT * INTO s FROM subscriber WHERE id = p_id FOR UPDATE;
    IF NOT FOUND OR s.status = 'erased' THEN
        RETURN 0;
    END IF;
    UPDATE outbox SET state = 'done', done_at = now()
    WHERE subscriber_id = p_id AND op <> 'delete' AND state IN ('pending', 'running');
    IF s.status <> 'pending' THEN
        INSERT INTO outbox (op, subscriber_id, idempotency_key, payload)
        VALUES ('unsubscribe', p_id, 'unsubscribe:' || p_id || '\\:erase',
                jsonb_build_object('listmonkSubscriberId', s.listmonk_subscriber_id,
                                   'emailEnc', encode(s.email_enc, 'base64')))
        ON CONFLICT (idempotency_key) DO NOTHING;
        INSERT INTO outbox (op, subscriber_id, idempotency_key, payload)
        VALUES ('delete', p_id, 'delete:' || p_id || '\\:0',
                jsonb_build_object('listmonkSubscriberId', s.listmonk_subscriber_id,
                                   'emailEnc', encode(s.email_enc, 'base64')))
        ON CONFLICT (idempotency_key) DO NOTHING;
    END IF;
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

_OLD = """
CREATE OR REPLACE FUNCTION privacy_erase_subscriber(p_id uuid) RETURNS integer
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


def upgrade() -> None:
    op.execute(_NEW)


def downgrade() -> None:
    op.execute(_OLD)
