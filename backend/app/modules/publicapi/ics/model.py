"""The input of the ICS writer: exactly the fields of the allowlist (`IcsRow`, E39)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class IcsRow:
    """One public event as the calendar needs it; built from a view row, field by field."""

    id: UUID
    slug: str
    title: str
    summary: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    starts_on: date | None
    ends_on: date | None
    tzid: str
    public_status: str
    public_seq: int
    updated_at: datetime
    public_reason_text: str | None
    venue_name: str | None
    venue_address: str | None
    venue_city: str | None
    category_slug: str | None
    category_name: str | None
    category_parent_slug: str | None
    category_parent_name: str | None
