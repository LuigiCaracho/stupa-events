"""Event models: `event`, `event_revision` and `event_status_event` (DDL in `0002`).

`event` is the dossier and carries the state machine. `state` changes only through
`PipelineService.fire`. `event_revision` and `event_status_event` are append-only: a
trigger refuses UPDATE, DELETE and TRUNCATE, and the runtime role has no such grant.
Users are stored as the OIDC `sub` of the principal.
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
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin
from app.modules.events.states import EventState, PublicStatus

EVENT_STATES = tuple(s.value for s in EventState)
PUBLIC_STATUSES = tuple(s.value for s in PublicStatus)
ORIGIN_KINDS = ("internal", "imported", "legacy", "mcp")
ACTOR_TYPES = ("human", "agent", "system")
FIELD_CLASSES = ("critical", "text", "dossier", "state")
CONTROL_CHARS = r"[\x01-\x1f\x7f-\x9f\u2028\u2029]"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Event(UUIDPkMixin, TimestampMixin, Base):
    """A dossier with its pipeline state, its critical fields and its poster."""

    __tablename__ = "event"

    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, server_default="idea")
    public_status: Mapped[str] = mapped_column(Text, server_default="scheduled")
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tzid: Mapped[str] = mapped_column(Text, server_default="Europe/Berlin")
    all_day: Mapped[bool] = mapped_column(Boolean, server_default="false")
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="RESTRICT"), nullable=True
    )
    venue_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    hero_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("attachment.id", ondelete="RESTRICT"), nullable=True
    )
    image_exception: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    origin_kind: Mapped[str] = mapped_column(Text, server_default="internal")
    rev: Mapped[int] = mapped_column(Integer, server_default="1")
    public_seq: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[str] = mapped_column(Text)
    submitted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(_in("state", EVENT_STATES), name="state"),
        CheckConstraint(_in("public_status", PUBLIC_STATUSES), name="public_status"),
        CheckConstraint(_in("origin_kind", ORIGIN_KINDS), name="origin_kind"),
        CheckConstraint("ends_at >= starts_at", name="time_order"),
        CheckConstraint("all_day = (starts_on IS NOT NULL)", name="all_day_days"),
        CheckConstraint(
            "state IN ('idea', 'withdrawn') OR organization_id IS NOT NULL", name="organization"
        ),
        CheckConstraint(f"title !~ '{CONTROL_CHARS}'", name="title_clean"),
        CheckConstraint(f"summary !~ '{CONTROL_CHARS}'", name="summary_clean"),
        CheckConstraint(f"venue_text !~ '{CONTROL_CHARS}'", name="venue_text_clean"),
        CheckConstraint("rev >= 1", name="rev"),
        Index("uq_event_slug", "slug", unique=True, postgresql_where=text("slug IS NOT NULL")),
        Index("ix_event_organization_id_starts_at", "organization_id", "starts_at"),
        Index("ix_event_state", "state"),
    )


class EventRevision(Base):
    """Full snapshot of an event per save (append-only)."""

    __tablename__ = "event_revision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("event.id", ondelete="RESTRICT"))
    rev: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(Text, server_default="human")
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_class: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("event_id", "rev", name="uq_event_revision_event_id_rev"),
        CheckConstraint(_in("actor_type", ACTOR_TYPES), name="actor_type"),
        CheckConstraint(_in("field_class", FIELD_CLASSES), name="field_class"),
    )


class EventStatusEvent(Base):
    """One state change of an event (append-only). `from_state` is NULL for T00."""

    __tablename__ = "event_status_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("event.id", ondelete="RESTRICT"))
    from_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_state: Mapped[str] = mapped_column(Text)
    transition_id: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(Text, server_default="human")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(_in("to_state", EVENT_STATES), name="to_state"),
        CheckConstraint(_in("actor_type", ACTOR_TYPES), name="actor_type"),
        CheckConstraint("note IS NULL OR length(note) <= 500", name="note_length"),
        Index("ix_event_status_event_event_id", "event_id"),
    )
