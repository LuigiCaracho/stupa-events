"""`geocode_cache`: one row per normalized query, hits and misses (migration `0013_maps`).

The row holds only an address or a place name, never a person. A hit is valid for 180 days, a
miss for 30. Only `events_app` can read the table; the public role cannot.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.modules.events.models import CONTROL_CHARS


class GeocodeCache(Base):
    """The answer of Nominatim for one query, or the fact that it found nothing."""

    __tablename__ = "geocode_cache"

    query_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    query_norm: Mapped[str] = mapped_column(Text)
    found: Mapped[bool] = mapped_column(Boolean)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    lon: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    osm_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    osm_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("found = (lat IS NOT NULL AND lon IS NOT NULL)", name="found_matches"),
        CheckConstraint(
            f"char_length(query_norm) <= 300 AND query_norm !~ '{CONTROL_CHARS}'",
            name="query_clean",
        ),
    )
