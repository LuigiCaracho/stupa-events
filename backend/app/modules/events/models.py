"""Event models: `event`, `event_revision` and `event_status_event` (DDL in `0002`).

`event` is the dossier with its three states. `state` changes only through the lifecycle
actions of `events.lifecycle`. `event_revision` and `event_status_event` are append-only: a
trigger refuses UPDATE, DELETE and TRUNCATE, and the runtime role has no such grant. The
status history keeps the state names of the pre-M5b pipeline (`LEGACY_STATES`).
Users are stored as the OIDC `sub` of the principal.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin
from app.modules.events.states import EventState, PublicStatus

EVENT_STATES = tuple(s.value for s in EventState)
PUBLIC_STATUSES = tuple(s.value for s in PublicStatus)
PUBLIC_REASON_CODES = ("none", "room", "speaker", "illness", "registration", "weather", "other")
LEGACY_STATES = ("idea", "planning", "in_review", "approved", "live", "followup", "withdrawn")
ORIGIN_KINDS = ("internal", "imported", "legacy", "mcp")
ACTOR_TYPES = ("human", "agent", "system")
CONTROL_CHARS = r"[\x01-\x1f\x7f-\x9f\u2028\u2029]"
LOCATION_PRECISIONS = ("exact", "building", "hidden")
EVENT_SEARCH_TSV = (
    "setweight(to_tsvector('de_unaccent'::regconfig, coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('de_unaccent'::regconfig, coalesce(summary, '')), 'B') || "
    "setweight(to_tsvector('de_unaccent'::regconfig, coalesce(description_md, '')), 'C')"
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Event(UUIDPkMixin, TimestampMixin, Base):
    """A dossier with its state, its base data and its poster."""

    __tablename__ = "event"

    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(Text, server_default="draft")
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
    origin_kind: Mapped[str] = mapped_column(Text, server_default="internal")
    rev: Mapped[int] = mapped_column(Integer, server_default="1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_seq: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[str] = mapped_column(Text)
    ticket_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("venue.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    public_reason_code: Mapped[str] = mapped_column(Text, server_default="none")
    public_reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_estimated: Mapped[bool] = mapped_column(Boolean, server_default="false")
    format_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("format.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("event.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    howto_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    howto_verified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    facts: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict)
    location_precision: Mapped[str] = mapped_column(Text, server_default="hidden", default="hidden")
    location_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    location_confirmed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(EVENT_SEARCH_TSV, persisted=True), nullable=True, deferred=True
    )

    __table_args__ = (
        CheckConstraint(_in("state", EVENT_STATES), name="state"),
        CheckConstraint(_in("location_precision", LOCATION_PRECISIONS), name="location_precision"),
        CheckConstraint("derived_from_id <> id", name="derived_from_self"),
        CheckConstraint("outcome IS NULL OR jsonb_typeof(outcome) = 'object'", name="outcome"),
        CheckConstraint("jsonb_typeof(facts) = 'object'", name="facts"),
        CheckConstraint(_in("public_reason_code", PUBLIC_REASON_CODES), name="public_reason_code"),
        CheckConstraint(
            "public_status <> 'scheduled' OR "
            "(public_reason_code = 'none' AND public_reason_text IS NULL)",
            name="public_reason_scheduled",
        ),
        CheckConstraint(_in("public_status", PUBLIC_STATUSES), name="public_status"),
        CheckConstraint(_in("origin_kind", ORIGIN_KINDS), name="origin_kind"),
        CheckConstraint("ends_at >= starts_at", name="time_order"),
        CheckConstraint("all_day = (starts_on IS NOT NULL)", name="all_day_days"),
        CheckConstraint("state = 'draft' OR organization_id IS NOT NULL", name="organization"),
        CheckConstraint("tzid = 'Europe/Berlin'", name="tzid"),
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
    snapshot: Mapped[dict] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("event_id", "rev", name="uq_event_revision_event_id_rev"),
        CheckConstraint(_in("actor_type", ACTOR_TYPES), name="actor_type"),
    )


class EventStatusEvent(Base):
    """One state change of an event (append-only). `from_state` is NULL for the creation."""

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
        CheckConstraint(_in("to_state", (*EVENT_STATES, *LEGACY_STATES)), name="to_state"),
        CheckConstraint(_in("actor_type", ACTOR_TYPES), name="actor_type"),
        CheckConstraint("note IS NULL OR length(note) <= 500", name="note_length"),
        Index("ix_event_status_event_event_id", "event_id"),
    )


class EditorDraft(Base):
    """Autosave draft of one person for one dossier (E21); never a revision."""

    __tablename__ = "editor_draft"

    owner_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    principal_sub: Mapped[str] = mapped_column(Text, primary_key=True)
    base_rev: Mapped[int] = mapped_column(Integer)
    fields: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("owner_kind IN ('event', 'document')", name="owner_kind"),)
