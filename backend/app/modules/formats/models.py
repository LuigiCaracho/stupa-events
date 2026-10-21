"""The `format` table: a recurring kind of event with a master howto (DDL in `0006`).

A format (Movienight, Campusfest) groups the editions of one event series-in-spirit and
carries the master howto that a new edition links to instead of copying it. Formats are
never deleted, only deactivated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin
from app.modules.events.models import CONTROL_CHARS

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,59}$"
FORMAT_SEARCH_TSV = (
    "setweight(to_tsvector('de_unaccent'::regconfig, coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('de_unaccent'::regconfig, coalesce(description_md, '')), 'C')"
)


class Format(UUIDPkMixin, TimestampMixin, Base):
    """A format with its defaults, its master howto and its last verification."""

    __tablename__ = "format"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="RESTRICT"), index=True
    )
    master_howto_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("document.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    defaults: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), default=dict)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(FORMAT_SEARCH_TSV, persisted=True), nullable=True, deferred=True
    )

    __table_args__ = (
        CheckConstraint(f"slug ~ '{SLUG_PATTERN}'", name="slug"),
        CheckConstraint(
            f"char_length(title) BETWEEN 1 AND 120 AND title !~ '{CONTROL_CHARS}'", name="title"
        ),
        CheckConstraint("jsonb_typeof(defaults) = 'object'", name="defaults"),
        CheckConstraint(
            "description_md IS NULL OR char_length(description_md) <= 20000", name="description"
        ),
        Index("ix_format_search_tsv", "search_tsv", postgresql_using="gin"),
    )
