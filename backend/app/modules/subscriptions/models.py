"""Subscription models: `interest`, `subscriber`, `subscription_profile`, `outbox`, lists, digests.

The DDL lives in migration `0009`. The address is stored only as `pgcrypto` ciphertext
(`email_enc`) and a keyed hash (`email_hmac`); tokens only as SHA-256 hex. Rows are removed
only by the `privacy_*` functions, the role `events_subs` has no `DELETE`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin

SUBSCRIBER_STATUSES = ("pending", "confirmed", "unsubscribed", "bounced", "erased")
OUTBOX_OPS = ("upsert", "unsubscribe", "delete", "ensure_list")
OUTBOX_STATES = ("pending", "running", "done", "dead")
DIGEST_STATUSES = ("draft", "released", "skipped")


class Interest(Base):
    """A questionnaire answer and the categories it stands for."""

    __tablename__ = "interest"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    category_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    sort: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")


class Subscriber(UUIDPkMixin, TimestampMixin, Base):
    """A mail subscription with its proof of consent; erased rows keep only a tombstone."""

    __tablename__ = "subscriber"

    email_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    email_hmac: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    confirm_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirm_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manage_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    manage_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_text_version: Mapped[str] = mapped_column(Text)
    consent_categories: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    listmonk_subscriber_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mails_day: Mapped[date] = mapped_column(Date, server_default=text("current_date"))
    mails_count: Mapped[int] = mapped_column(Integer, server_default="0")


class SubscriptionProfile(UUIDPkMixin, TimestampMixin, Base):
    """The answers of one person, resolved to categories, with the hash of the calendar token."""

    __tablename__ = "subscription_profile"

    subscriber_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriber.id", ondelete="SET NULL"), nullable=True
    )
    questionnaire_version: Mapped[int] = mapped_column(Integer)
    interests: Mapped[list[str]] = mapped_column(JSONB)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text))
    ics_token_hash: Mapped[str] = mapped_column(Text)
    ics_token_rotated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    mail_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_fetched_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class Outbox(UUIDPkMixin, Base):
    """A pending change for Listmonk; the worker brings Listmonk to the wanted state."""

    __tablename__ = "outbox"

    op: Mapped[str] = mapped_column(Text)
    subscriber_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("subscriber.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    state: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ListmonkList(Base):
    """The Listmonk list of a category slug (or `_all`)."""

    __tablename__ = "listmonk_list"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    listmonk_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DigestRun(UUIDPkMixin, Base):
    """The weekly digest draft of one list."""

    __tablename__ = "digest_run"

    week_start: Mapped[date] = mapped_column(Date)
    list_key: Mapped[str] = mapped_column(Text)
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    event_count: Mapped[int] = mapped_column(Integer)
    released_by_sub: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
