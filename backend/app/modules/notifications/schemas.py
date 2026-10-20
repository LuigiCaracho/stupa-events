"""Wire shapes of the inbox API (camelCase, no extra members)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.auth.schemas import CamelModel


class NotificationOut(CamelModel):
    """One inbox entry."""

    id: UUID
    kind: str
    event_id: UUID | None
    event_title: str | None
    params: dict[str, Any]
    link: str
    created_at: datetime
    read_at: datetime | None


class NotificationPage(CamelModel):
    """A page of the inbox, newest first."""

    items: list[NotificationOut]
    next_cursor: str | None


class UnreadCount(CamelModel):
    """The number of unread entries."""

    count: int
