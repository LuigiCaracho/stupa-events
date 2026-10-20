"""Inbox queries: list with keyset cursor, unread count, mark read.

The cursor is `<created_at ISO>|<id>` of the last row, URL-safe base64. Only the owner sees
a row; a foreign or unknown id is indistinguishable (404 at the router).
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models import Event
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationOut, NotificationPage
from app.shared.errors import BadRequestError

DEFAULT_LIMIT = 30
MAX_LIMIT = 100


def encode_cursor(created_at: datetime, nid: UUID) -> str:
    """Encode the position after a row."""
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{nid}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode a cursor.

    Raises:
        BadRequestError: The cursor is malformed.
    """
    try:
        stamp, raw_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), UUID(raw_id)
    except ValueError as exc:
        raise BadRequestError("Invalid cursor.", code="invalid_cursor") from exc


async def list_notifications(
    session: AsyncSession,
    sub: str,
    *,
    unread: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> NotificationPage:
    """Return one page of the person's inbox, newest first."""
    query = (
        select(Notification, Event.title)
        .outerjoin(Event, Event.id == Notification.event_id)
        .where(Notification.recipient_sub == sub)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit + 1)
    )
    if unread:
        query = query.where(Notification.read_at.is_(None))
    if cursor:
        query = query.where(
            tuple_(Notification.created_at, Notification.id) < tuple_(*decode_cursor(cursor))
        )
    rows = (await session.execute(query)).all()
    page = rows[:limit]
    items = [
        NotificationOut(
            id=n.id,
            kind=n.kind,
            event_id=n.event_id,
            event_title=title,
            params=n.params,
            link=n.link,
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n, title in page
    ]
    more = len(rows) > limit
    last = page[-1][0] if more else None
    return NotificationPage(
        items=items, next_cursor=encode_cursor(last.created_at, last.id) if last else None
    )


async def unread_count(session: AsyncSession, sub: str) -> int:
    """Count the unread entries of the person."""
    stmt = select(func.count()).where(
        Notification.recipient_sub == sub, Notification.read_at.is_(None)
    )
    return int((await session.execute(stmt)).scalar_one())


async def mark_read(session: AsyncSession, sub: str, nid: UUID) -> bool:
    """Mark one own entry read (idempotent). Return False for a foreign or unknown id."""
    owned = await session.execute(
        select(Notification.id).where(Notification.id == nid, Notification.recipient_sub == sub)
    )
    if owned.scalar_one_or_none() is None:
        return False
    await session.execute(
        update(Notification)
        .where(Notification.id == nid, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    return True


async def mark_all_read(session: AsyncSession, sub: str) -> None:
    """Mark every unread entry of the person read."""
    await session.execute(
        update(Notification)
        .where(Notification.recipient_sub == sub, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
