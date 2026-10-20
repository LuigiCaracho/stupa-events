"""Notification tables: `notification` (inbox) and `notification_pref` (per kind).

`params` holds display values only (dossier title, actor name, counters), never free text
from a comment. DDL lives in migration `0005_dossier_knowledge`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPkMixin
from app.modules.notifications.kinds import NOTIFICATION_KINDS

_KIND_LIST = ", ".join(repr(k) for k in NOTIFICATION_KINDS)


class Notification(UUIDPkMixin, Base):
    """One inbox entry of one person."""

    __tablename__ = "notification"

    recipient_sub: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("event.id", ondelete="RESTRICT"), nullable=True
    )
    params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    link: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(f"kind IN ({_KIND_LIST})", name="kind"),
        CheckConstraint(r"link ~ '^/[^/\\]'", name="link"),
        Index("ix_notification_recipient_sub_created_at", "recipient_sub", text("created_at DESC")),
        Index(
            "ix_notification_unread",
            "recipient_sub",
            postgresql_where=text("read_at IS NULL"),
        ),
    )


class NotificationPref(Base):
    """Channel switches of one person for one kind; a missing row means everything on."""

    __tablename__ = "notification_pref"

    principal_sub: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    in_app: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    mail: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint(f"kind IN ({_KIND_LIST})", name="kind"),)
