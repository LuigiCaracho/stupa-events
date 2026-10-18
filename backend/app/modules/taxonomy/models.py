"""Categories and venues: the `category` table (migration `0002_events_core`) and `venue` (`0003`).

A category is a format (`kino`), a faculty group (`fachschaft`) or a partner. A venue is a
place of the archive with an optional address and optional coordinates. Neither is ever
deleted, only deactivated. `color_token` is a token name, never a hex value.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin, UUIDPkMixin
from app.modules.events.models import CONTROL_CHARS

CATEGORY_KINDS = ("format", "fachschaft", "partner")
REQUIRED_PROFILES = ("generic", "party", "meeting", "trip")
COLOR_TOKENS = ("orange", "blue", "petrol", "navy", "yellow", "red")
PUBLIC_PRECISIONS = ("exact", "building", "hidden")
GEOCODE_SOURCES = ("pin", "nominatim", "import")


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


class Venue(UUIDPkMixin, TimestampMixin, Base):
    """A place of events; `address`, `lat` and `lon` stay empty until someone knows them."""

    __tablename__ = "venue"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    postcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    building_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    campus_building_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    public_precision: Mapped[str] = mapped_column(Text, server_default="hidden")
    is_private: Mapped[bool] = mapped_column(Boolean, server_default="false")
    geocode_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legacy_wp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        CheckConstraint(
            "public_precision IN (" + ", ".join(repr(p) for p in PUBLIC_PRECISIONS) + ")",
            name="public_precision",
        ),
        CheckConstraint(
            "geocode_source IS NULL OR geocode_source IN ("
            + ", ".join(repr(g) for g in GEOCODE_SOURCES)
            + ")",
            name="geocode_source",
        ),
        CheckConstraint("(lat IS NULL) = (lon IS NULL)", name="coordinates_pair"),
        CheckConstraint(
            "(lat IS NULL OR lat BETWEEN -90 AND 90) AND (lon IS NULL OR lon BETWEEN -180 AND 180)",
            name="coordinates_range",
        ),
        CheckConstraint(f"name !~ '{CONTROL_CHARS}'", name="name_clean"),
        CheckConstraint(f"address !~ '{CONTROL_CHARS}'", name="address_clean"),
        CheckConstraint(f"notes !~ '{CONTROL_CHARS}'", name="notes_clean"),
    )
