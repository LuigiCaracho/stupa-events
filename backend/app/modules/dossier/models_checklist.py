"""Checklist templates and the checklist items of a dossier (DDL in ``0005_dossier_knowledge``).

A template belongs to a category or a facts profile. Applying it copies its items into
`checklist_item`, keyed by `(event_id, template_item_id)` so that applying twice adds nothing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UUIDPkMixin

PHASES = ("planning", "review", "live", "followup")
PROFILES = ("generic", "party", "meeting", "trip")
_PHASE_SQL = "phase IN ('planning', 'review', 'live', 'followup')"


class ChecklistTemplate(UUIDPkMixin, Base):
    """A checklist template of one category or one facts profile."""

    __tablename__ = "checklist_template"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    profile: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "profile IS NULL OR profile IN ('generic', 'party', 'meeting', 'trip')", name="profile"
        ),
        CheckConstraint("num_nonnulls(category_id, profile) <= 1", name="owner"),
    )


class ChecklistTemplateItem(UUIDPkMixin, Base):
    """One item of a template, stable through `key`."""

    __tablename__ = "checklist_template_item"

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checklist_template.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("template_id", "key", name="uq_checklist_template_item_key"),
        CheckConstraint(_PHASE_SQL, name="phase"),
        CheckConstraint("due_offset_days BETWEEN -365 AND 365", name="offset"),
    )


class ChecklistItem(UUIDPkMixin, Base):
    """One checklist item of a dossier."""

    __tablename__ = "checklist_item"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event.id", ondelete="RESTRICT"), nullable=False
    )
    template_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("checklist_template_item.id", ondelete="RESTRICT"), nullable=True
    )
    position: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    assignee_sub: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_manual: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    waived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notified_due_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("event_id", "template_item_id", name="uq_checklist_item_template"),
        CheckConstraint(_PHASE_SQL, name="phase"),
        CheckConstraint("char_length(text) BETWEEN 1 AND 200", name="text"),
        CheckConstraint("done_at IS NULL OR waived_reason IS NULL", name="done_or_waived"),
        CheckConstraint(
            "waived_reason IS NULL OR btrim(waived_reason) <> ''", name="waived_reason"
        ),
        Index("ix_checklist_item_event_phase", "event_id", "phase"),
        Index(
            "ix_checklist_item_assignee_open",
            "assignee_sub",
            postgresql_where=sql_text("done_at IS NULL AND waived_reason IS NULL"),
        ),
    )
