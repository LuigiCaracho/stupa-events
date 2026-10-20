"""Review comments of a dossier (DDL in migration ``0005_dossier_knowledge``).

A root comment may carry an anchor (`field`, `attachmentId`, `checklistItemId` or
`documentId` with offsets); replies hang under a root. Only the resolution columns ever
change (trigger `comment_immutable`); there is no delete.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPkMixin

ANCHOR_CHECK = (
    "anchor IS NULL OR (jsonb_typeof(anchor) = 'object' AND (anchor ? 'field' "
    "OR anchor ? 'attachmentId' OR anchor ? 'checklistItemId' OR anchor ? 'documentId'))"
)


class Comment(UUIDPkMixin, Base):
    """A comment or a reply on a dossier."""

    __tablename__ = "comment"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="RESTRICT"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comment.id", ondelete="RESTRICT"), nullable=True
    )
    author_sub: Mapped[str] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(Text, server_default="human", default="human")
    body_md: Mapped[str] = mapped_column(Text)
    anchor: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("actor_type IN ('human', 'agent', 'system')", name="actor_type"),
        CheckConstraint("char_length(body_md) BETWEEN 1 AND 4000", name="body_md"),
        CheckConstraint(ANCHOR_CHECK, name="anchor"),
        Index("ix_comment_event_id", "event_id"),
        Index(
            "ix_comment_open",
            "event_id",
            postgresql_where=text("resolved_at IS NULL AND parent_id IS NULL"),
        ),
    )
