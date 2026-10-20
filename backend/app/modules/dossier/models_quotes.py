"""Comparison quotes of a dossier (DDL in migration ``0005_dossier_knowledge``).

One selected quote per group (partial unique index). Quotes are never deleted, `retired_at`
hides them. The amounts live only here and never reach revisions, cards, the feed or audit.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPkMixin


class Quote(UUIDPkMixin, Base):
    """A vendor quote inside a comparison group."""

    __tablename__ = "quote"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="RESTRICT"), nullable=False
    )
    grp: Mapped[str] = mapped_column(Text)
    vendor: Mapped[str] = mapped_column(Text)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, server_default="EUR", default="EUR")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attachment.id", ondelete="RESTRICT"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency"),
        CheckConstraint("char_length(grp) BETWEEN 1 AND 60", name="grp"),
        CheckConstraint("char_length(vendor) BETWEEN 1 AND 120", name="vendor"),
        CheckConstraint("note IS NULL OR char_length(note) <= 500", name="note"),
        Index("ix_quote_event_id", "event_id"),
        Index(
            "uq_quote_selected",
            "event_id",
            "grp",
            unique=True,
            postgresql_where=text("selected AND retired_at IS NULL"),
        ),
    )
