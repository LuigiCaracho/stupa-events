"""arq job `gc_geocode_cache`: drop geocode answers past their validity, once a day.

A hit lives 180 days, a miss 30 (`app.modules.geocode.service`). Only this job deletes from
`geocode_cache`; `events_app` has `DELETE` on the table for it.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, and_, delete, or_

from app.db import get_sessionmaker
from app.modules.geocode.models import GeocodeCache
from app.modules.geocode.service import HIT_DAYS, MISS_DAYS
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.geocode")


async def gc_geocode_cache(ctx: dict[str, Any]) -> str:
    """Delete hits older than 180 days and misses older than 30 days; return the log line."""
    now = utcnow()
    maker = ctx.get("gc_sessionmaker") or get_sessionmaker()
    async with maker() as session:
        result = await session.execute(
            delete(GeocodeCache).where(
                or_(
                    and_(
                        GeocodeCache.found, GeocodeCache.fetched_at < now - timedelta(days=HIT_DAYS)
                    ),
                    and_(
                        GeocodeCache.found.is_(False),
                        GeocodeCache.fetched_at < now - timedelta(days=MISS_DAYS),
                    ),
                )
            )
        )
        await session.commit()
    line = f"gc_geocode_cache: deleted={cast(CursorResult[Any], result).rowcount or 0}"
    logger.info(line)
    return line
