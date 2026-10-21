"""Event slugs: `<YYYY-MM-DD>-<title>` in local time, suffix `-2`, `-3` on a collision."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models import Event
from app.shared.search import escape_like
from app.shared.timeutil import local_date_iso

MAX_TITLE_PART = 60
_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Turn a title into an ASCII slug part (German umlauts become digraphs)."""
    folded = unicodedata.normalize("NFKD", title.lower().translate(_GERMAN))
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return _NON_ALNUM.sub("-", ascii_only).strip("-")[:MAX_TITLE_PART].strip("-") or "event"


def base_slug(title: str, starts_at: datetime, tzid: str) -> str:
    """Return the slug without a collision suffix."""
    return f"{local_date_iso(starts_at, tzid)}-{slugify(title)}"


async def unique_slug(session: AsyncSession, base: str) -> str:
    """Return `base` or `base-N` with the smallest free N >= 2."""
    taken = set(
        await session.scalars(
            select(Event.slug).where(Event.slug.like(f"{escape_like(base)}%", escape="\\"))
        )
    )
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"
