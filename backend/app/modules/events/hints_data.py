"""Loader of the hint inputs: builds a `HintInput` per dossier with a few grouped queries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dossier.models_documents import Document
from app.modules.events import facts
from app.modules.events.access import location_is_confirmed
from app.modules.events.hints import HintInput, PosterFacts
from app.modules.events.models import Event
from app.modules.files.models import Attachment
from app.modules.formats.models import Format
from app.modules.taxonomy.models import Category
from app.shared.timeutil import utcnow


async def howto_presence(session: AsyncSession, events: Sequence[Event]) -> set[UUID]:
    """Return the ids of the dossiers with a howto of their own or the master howto of a format."""
    own = await session.scalars(
        select(Document.event_id).where(
            Document.event_id.in_([e.id for e in events]), Document.kind == "howto"
        )
    )
    format_ids = {e.format_id for e in events if e.format_id}
    mastered = (
        set(
            await session.scalars(
                select(Format.id).where(
                    Format.id.in_(format_ids), Format.master_howto_document_id.is_not(None)
                )
            )
        )
        if format_ids
        else set()
    )
    return {i for i in own if i is not None} | {e.id for e in events if e.format_id in mastered}


def poster_facts(poster: Attachment | None) -> PosterFacts | None:
    """Reduce a poster row to the facts the hints read; a retired poster counts as none."""
    if poster is None or poster.retired_at is not None:
        return None
    return PosterFacts(
        scan_status=poster.scan_status,
        has_derivatives=bool(poster.derivatives),
        alt_text=poster.alt_text,
        credit=poster.credit,
        persons_depicted=poster.persons_depicted,
        consent_note=poster.consent_note,
    )


def outcome_answered(outcome: Mapping[str, object] | None) -> bool:
    """Tell if the outcome holds a waiver or at least one figure or note."""
    if not outcome:
        return False
    keys = ("attendance", "costsCents", "revenueCents", "notes")
    return bool(outcome.get("waived")) or any(outcome.get(key) is not None for key in keys)


async def hint_inputs(
    session: AsyncSession,
    events: Sequence[Event],
    posters: Mapping[UUID, Attachment],
    categories: Mapping[UUID, Category],
    *,
    now: datetime | None = None,
) -> dict[UUID, HintInput]:
    """Build the hint input of every dossier; `posters` and `categories` are already loaded."""
    if not events:
        return {}
    moment = now or utcnow()
    howtos = await howto_presence(session, events)
    result: dict[UUID, HintInput] = {}
    for event in events:
        category = categories.get(event.primary_category_id) if event.primary_category_id else None
        result[event.id] = HintInput(
            state=event.state,
            now=moment,
            ends_at=event.ends_at,
            summary=event.summary,
            primary_category_id=event.primary_category_id,
            venue_id=event.venue_id,
            venue_text=event.venue_text,
            location_confirmed=location_is_confirmed(event),
            poster=poster_facts(posters.get(event.hero_attachment_id))
            if event.hero_attachment_id
            else None,
            facts_error=facts.error_for(
                category.required_profile if category else "generic", event.facts
            ),
            howto_present=event.id in howtos,
            outcome_answered=outcome_answered(event.outcome),
        )
    return result
