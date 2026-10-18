"""The one optimistic UPDATE of a dossier: `WHERE id AND rev [AND state IN ...]`."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event


async def update_event(
    session: AsyncSession,
    event: Event,
    values: dict[str, Any],
    *,
    states: Collection[str] | None = None,
) -> Event:
    """Write `values` and raise `rev` by one, if the dossier is still at `event.rev`.

    Args:
        session: The open session (no commit).
        event: The row as the caller read it.
        values: Columns to set.
        states: Optional states the row must still be in.

    Raises:
        VersionConflict: The row changed in the meantime; it carries the current row.
    """
    condition = [Event.id == event.id, Event.rev == event.rev]
    if states is not None:
        condition.append(Event.state.in_(list(states)))
    result = await session.execute(
        update(Event)
        .where(*condition)
        .values(**values, rev=Event.rev + 1)
        .returning(Event)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        await session.refresh(event)
        raise VersionConflict(event)
    return updated
