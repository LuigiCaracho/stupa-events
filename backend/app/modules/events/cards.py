"""Build `EventCard` rows with batched lookups: references, people, hints and open questions."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.dossier.models_comments import Comment
from app.modules.events.card_schemas import EventCard, PersonRef
from app.modules.events.hints import missing_info, warning_count
from app.modules.events.hints_data import hint_inputs, howto_presence
from app.modules.events.models import Event
from app.modules.events.presenter import howto_unverified
from app.modules.files.models import Attachment
from app.modules.formats.models import Format
from app.modules.orgs.models import Organization
from app.modules.orgs.schemas import OrgRef
from app.modules.orgs.scope import bind
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.schemas import CategoryRef


async def _by_id[T](session: AsyncSession, model: type[T], ids: set) -> dict:
    if not ids:
        return {}
    rows = await session.scalars(select(model).where(model.id.in_(ids)))  # type: ignore[attr-defined]
    return {row.id: row for row in rows}  # type: ignore[attr-defined]


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all()) if subs else {}


async def _open_questions(session: AsyncSession, events: Sequence[Event]) -> dict:
    rows = await session.execute(
        select(Comment.event_id, func.count())
        .where(
            Comment.event_id.in_([e.id for e in events]),
            Comment.parent_id.is_(None),
            Comment.resolved_at.is_(None),
        )
        .group_by(Comment.event_id)
    )
    return dict(rows.all())


def _venue_label(event: Event, venue: Venue | None) -> str | None:
    if venue is None:
        return event.venue_text
    return None if venue.is_private else venue.name


async def present_cards(
    session: AsyncSession, principal: Principal, events: Sequence[Event]
) -> list[EventCard]:
    """Turn events into cards, reading references, posters and names once."""
    await bind(session, principal)
    if not events:
        return []
    orgs = await _by_id(
        session, Organization, {e.organization_id for e in events if e.organization_id}
    )
    categories = await _by_id(
        session, Category, {e.primary_category_id for e in events if e.primary_category_id}
    )
    venues = await _by_id(session, Venue, {e.venue_id for e in events if e.venue_id})
    posters = await _by_id(
        session, Attachment, {e.hero_attachment_id for e in events if e.hero_attachment_id}
    )
    formats = await _by_id(session, Format, {e.format_id for e in events if e.format_id})
    names = await _names(session, {e.created_by for e in events})
    inputs = await hint_inputs(session, events, posters, categories)
    questions = await _open_questions(session, events)
    howtos = await howto_presence(session, events)
    return [
        EventCard(
            id=e.id,
            title=e.title,
            state=e.state,
            public_status=e.public_status,  # type: ignore[arg-type]
            starts_at=e.starts_at,
            ends_at=e.ends_at,
            tzid=e.tzid,
            organization=OrgRef.model_validate(orgs[e.organization_id])
            if e.organization_id in orgs
            else None,
            venue_label=_venue_label(e, venues.get(e.venue_id)),
            primary_category=CategoryRef.model_validate(categories[e.primary_category_id])
            if e.primary_category_id in categories
            else None,
            has_poster=inputs[e.id].poster is not None,
            created_by=PersonRef(sub=e.created_by, display_name=names.get(e.created_by)),
            rev=e.rev,
            open_questions=questions.get(e.id, 0),
            hint_count=warning_count(missing_info(inputs[e.id])),
            all_day=e.all_day,
            format_slug=formats[e.format_id].slug if e.format_id in formats else None,
            howto_unverified=howto_unverified(e, e.id in howtos),
        )
        for e in events
    ]
