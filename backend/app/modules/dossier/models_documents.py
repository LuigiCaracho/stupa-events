"""Documents of a dossier (howto, notes, mail templates) and their append-only revisions.

`document` holds the newest text as a copy; `document_revision` holds every saved version
(DDL in migration ``0005_dossier_knowledge``). Autosave never creates a revision.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPkMixin

DOCUMENT_KINDS = ("howto", "retrospective", "notes", "mail_template")
DOCUMENT_VISIBILITIES = ("team", "org", "shared")
MAX_BODY_CHARS = 200_000


class Document(UUIDPkMixin, Base):
    """One text document of a dossier."""

    __tablename__ = "document"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text, server_default="", default="")
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}", default=dict)
    visibility: Mapped[str] = mapped_column(Text, server_default="org", default="org")
    carry_over: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    rev: Mapped[int] = mapped_column(Integer, server_default="1", default=1)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "kind IN ('howto', 'retrospective', 'notes', 'mail_template')", name="kind"
        ),
        CheckConstraint("visibility IN ('team', 'org', 'shared')", name="visibility"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title"),
        CheckConstraint(f"char_length(body_md) <= {MAX_BODY_CHARS}", name="body_md"),
        Index("ix_document_event_id", "event_id"),
        Index(
            "uq_document_event_howto",
            "event_id",
            unique=True,
            postgresql_where=text("kind = 'howto'"),
        ),
    )


class DocumentRevision(Base):
    """One saved version of a document; rows are never changed or deleted."""

    __tablename__ = "document_revision"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.id", ondelete="RESTRICT"), nullable=False
    )
    rev: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}", default=dict)
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(Text, server_default="human", default="human")
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("document_id", "rev", name="pk_document_revision"),
        CheckConstraint("actor_type IN ('human', 'agent', 'system')", name="actor_type"),
        CheckConstraint("change_note IS NULL OR char_length(change_note) <= 500", name="note"),
    )
