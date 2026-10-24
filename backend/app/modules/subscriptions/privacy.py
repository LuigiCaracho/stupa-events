"""Retention jobs: call the `privacy_*` functions and write one audit entry per non-zero count.

Personal data leaves the database only through these `SECURITY DEFINER` functions; the role
`events_subs` has no `DELETE`. Cutoffs (PLAN 8.9): pending sign-ups after 48 hours, unsubscribed or
bounced addresses after 30 days, calendar-only profiles 12 months after the last fetch, finished
outbox rows after 30 days. The audit entry holds the action and the count only, written through
the application connection (`events_app`), because the subs role never writes the audit chain.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.audit.service import record as audit_record
from app.shared.timeutil import utcnow

logger = logging.getLogger("app.subscriptions.privacy")

Maker = async_sessionmaker[AsyncSession]

PENDING_TTL = timedelta(hours=48)
UNSUBSCRIBED_TTL = timedelta(days=30)
PROFILE_TTL = timedelta(days=365)
OUTBOX_TTL = timedelta(days=30)


async def purge_expired(subs: Maker, app: Maker, *, now: datetime | None = None) -> dict[str, int]:
    """Run the four retention functions and audit every non-zero count.

    Returns:
        Counts by action: `pending`, `unsubscribed`, `profiles`, `outbox`.
    """
    moment = now or utcnow()
    calls = {
        "pending": func.privacy_purge_pending(moment - PENDING_TTL),
        "unsubscribed": func.privacy_anonymize_unsubscribed(moment - UNSUBSCRIBED_TTL),
        "profiles": func.privacy_purge_profiles((moment - PROFILE_TTL).date()),
        "outbox": func.privacy_purge_outbox(moment - OUTBOX_TTL),
    }
    counts: dict[str, int] = {}
    for name, call in calls.items():
        async with subs.begin() as session:
            counts[name] = int(await session.scalar(select(call)) or 0)
    async with app.begin() as session:
        for name, count in counts.items():
            if count:
                await audit_record(
                    session,
                    actor=None,
                    action=f"privacy.purge_{name}",
                    data={"count": count, "by": "system"},
                )
    logger.info("privacy purge %s", counts)
    return counts


async def erase_subscriber(subs: Maker, app: Maker, subscriber_id: object, *, by: str) -> bool:
    """Erase one subscriber through `privacy_erase_subscriber` and audit it; True if it existed."""
    async with subs.begin() as session:
        erased = int(
            await session.scalar(select(func.privacy_erase_subscriber(subscriber_id))) or 0
        )
    async with app.begin() as session:
        await audit_record(
            session,
            actor=by,
            action="subscriber.erase",
            data={"found": bool(erased), "by": by},
        )
    return bool(erased)
