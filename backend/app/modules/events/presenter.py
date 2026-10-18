"""Build the wire shape `EventOut` from event rows with batched lookups."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier.schemas import attachment_out
from app.modules.events.access import snapshot_of
from app.modules.events.models import Event
from app.modules.events.schemas import EventOut, ImageExceptionOut
from app.modules.files.models import Attachment
from app.modules.orgs.models import Organization
from app.modules.orgs.schemas import OrgRef
from app.modules.orgs.scope import bind
from app.modules.pipeline.snapshot import actor_of
from app.modules.pipeline.transitions import allowed_transitions
from app.modules.taxonomy.models import Category
from app.modules.taxonomy.schemas import CategoryRef


def _exception_out(raw: dict | None) -> ImageExceptionOut | None:
    if not raw:
        return None
    return ImageExceptionOut(
        granted_by=raw["granted_by"], reason=raw["reason"], at=datetime.fromisoformat(raw["at"])
    )


async def present(
    session: AsyncSession, principal: Principal, events: Sequence[Event]
) -> list[EventOut]:
    """Turn events into `EventOut`, reading organizations, categories and posters once."""
    await bind(session, principal)
    org_ids = {e.organization_id for e in events if e.organization_id}
    category_ids = {e.primary_category_id for e in events if e.primary_category_id}
    poster_ids = {e.hero_attachment_id for e in events if e.hero_attachment_id}
    orgs = (
        {
            o.id: o
            for o in (
                await session.scalars(select(Organization).where(Organization.id.in_(org_ids)))
            )
        }
        if org_ids
        else {}
    )
    categories = (
        {
            c.id: c
            for c in (await session.scalars(select(Category).where(Category.id.in_(category_ids))))
        }
        if category_ids
        else {}
    )
    posters = (
        {
            a.id: a
            for a in (
                await session.scalars(select(Attachment).where(Attachment.id.in_(poster_ids)))
            )
        }
        if poster_ids
        else {}
    )
    return [_one(principal, e, orgs, categories, posters) for e in events]


def _one(
    principal: Principal,
    event: Event,
    orgs: dict,
    categories: dict,
    posters: dict,
) -> EventOut:
    poster = posters.get(event.hero_attachment_id)
    org = orgs.get(event.organization_id)
    category = categories.get(event.primary_category_id)
    actor = actor_of(principal, event.organization_id)
    return EventOut(
        id=event.id,
        slug=event.slug,
        state=event.state,
        public_status=event.public_status,  # type: ignore[arg-type]
        title=event.title,
        summary=event.summary,
        description_md=event.description_md,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        tzid=event.tzid,
        all_day=event.all_day,
        organization=OrgRef.model_validate(org) if org else None,
        venue_text=event.venue_text,
        primary_category=CategoryRef.model_validate(category) if category else None,
        poster=attachment_out(poster) if poster else None,
        image_exception=_exception_out(event.image_exception),
        rev=event.rev,
        created_by=event.created_by,
        submitted_by=event.submitted_by,
        approved_by=event.approved_by,
        created_at=event.created_at,
        updated_at=event.updated_at,
        allowed_transitions=allowed_transitions(snapshot_of(event, poster), actor),  # type: ignore[arg-type]
    )
