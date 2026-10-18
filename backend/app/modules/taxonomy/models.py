"""Categories: the `category` table (DDL in migration `0002_events_core`).

A category is a format (`kino`), a faculty group (`fachschaft`) or a partner. It is never
deleted, only deactivated. `color_token` is a token name, never a hex value.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin

CATEGORY_KINDS = ("format", "fachschaft", "partner")
REQUIRED_PROFILES = ("generic", "party", "meeting", "trip")


class Category(UUIDPkMixin, TimestampMixin, Base):
    """One category of the schema A (format, faculty group or partner)."""

    __tablename__ = "category"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    short: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_profile: Mapped[str] = mapped_column(Text, server_default="generic")
    legacy_wp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        CheckConstraint("kind IN ('format', 'fachschaft', 'partner')", name="kind"),
        CheckConstraint(
            "required_profile IN ('generic', 'party', 'meeting', 'trip')", name="required_profile"
        ),
    )
