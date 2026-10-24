"""Profiles: create one from resolved answers, build the calendar addresses, rotate the token."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.interests import Catalog, Resolution
from app.modules.subscriptions.models import SubscriptionProfile
from app.modules.subscriptions.schemas import ProfileCategory
from app.modules.subscriptions.tokens import hash_token, new_token
from app.settings import Settings


def calendar_urls(settings: Settings, token: str) -> tuple[str, str]:
    """Return the `https` address of a profile calendar and its `webcal` twin."""
    https = f"{settings.public_base_url.rstrip('/')}/ics/p/{token}.ics"
    return https, "webcal:" + https.partition(":")[2]


def category_refs(catalog: Catalog, slugs: Sequence[str]) -> list[ProfileCategory]:
    """Name the categories (unknown or inactive ones are left out)."""
    return [
        ProfileCategory(slug=s, name=catalog.categories[s].name)
        for s in slugs
        if s in catalog.categories
    ]


async def create_profile(
    session: AsyncSession, resolution: Resolution, questionnaire_version: int
) -> tuple[UUID, str]:
    """Insert a calendar-only profile and return its id and the token (shown once)."""
    token = new_token()
    result = await session.execute(
        insert(SubscriptionProfile)
        .values(
            questionnaire_version=questionnaire_version,
            interests=list(resolution.interests),
            categories=list(resolution.categories),
            ics_token_hash=hash_token(token),
        )
        .returning(SubscriptionProfile.id)
    )
    return result.scalar_one(), token


async def rotate_token(session: AsyncSession, profile_id: UUID) -> str:
    """Replace the calendar token; the old hash is overwritten, so the old token is unknown."""
    token = new_token()
    await session.execute(
        update(SubscriptionProfile)
        .where(SubscriptionProfile.id == profile_id)
        .values(
            ics_token_hash=hash_token(token),
            ics_token_rotated_at=func.now(),
            updated_at=func.now(),
        )
    )
    return token
