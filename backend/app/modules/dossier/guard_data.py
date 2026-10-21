"""The M4 inputs of the guards, read for many dossiers with a few grouped queries.

`open_comments` counts open root comments, `open_hero_comments` those anchored on the
poster field or on any file in the replacement chain of the current poster (so replacing the
poster does not dissolve a question), `open_required_checklist` and `open_required_followup`
the required items of the phases `planning` and `followup`, `quarantined_attachments` the
unscanned posters, social posts and shared files except the hero (which `image_required`
reports), `poster_reused` the flyer check: the same file in a dossier of another year, or a
printed date of another year. M5 adds the follow-up inputs: `retrospective_filled` (a
retrospective document with text), `howto_present` (a dossier howto or the master howto of
its format) and the facts profile of the main category.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.dossier.models_comments import Comment
from app.modules.dossier.models_documents import Document
from app.modules.events.models import Event
from app.modules.files.models import Attachment
from app.modules.formats.models import Format
from app.modules.taxonomy.models import Category
from app.shared.timeutil import DEFAULT_TZID, to_local

_HERO_CHAIN = text(
    """
    WITH RECURSIVE chain(event_id, id) AS (
        SELECT e.id, e.hero_attachment_id FROM event e
        WHERE e.id = ANY(:ids) AND e.hero_attachment_id IS NOT NULL
      UNION
        SELECT c.event_id, a.id
        FROM chain c
        JOIN attachment x ON x.id = c.id
        JOIN attachment a ON a.supersedes_id = c.id OR a.id = x.supersedes_id
    )
    SELECT cm.event_id, count(*) FROM comment cm
    WHERE cm.event_id = ANY(:ids) AND cm.parent_id IS NULL AND cm.resolved_at IS NULL
      AND (cm.anchor ->> 'field' = 'hero' OR EXISTS (
            SELECT 1 FROM chain ch
            WHERE ch.event_id = cm.event_id AND ch.id::text = cm.anchor ->> 'attachmentId'))
    GROUP BY cm.event_id
    """
)


@dataclass(frozen=True, slots=True)
class GuardData:
    """The per-dossier values of the M4 guards (neutral when nothing is found)."""

    open_comments: int = 0
    open_hero_comments: int = 0
    open_required_checklist: int = 0
    open_required_followup: int = 0
    quarantined_attachments: int = 0
    poster_reused: bool = False
    retrospective_filled: bool = False
    howto_present: bool = False
    required_profile: str = "generic"


async def _counts(session: AsyncSession, statement: Select[UUID, int]) -> dict[UUID, int]:
    return {row[0]: row[1] for row in (await session.execute(statement)).all()}


async def _poster_reused(
    session: AsyncSession, events: Sequence[Event], starts_at: dict[UUID, datetime]
) -> set[UUID]:
    hero, other, other_event = aliased(Attachment), aliased(Attachment), aliased(Event)
    ids = [e.id for e in events]
    other_year = func.extract("year", func.timezone(DEFAULT_TZID, other_event.starts_at))
    shared = await session.execute(
        select(Event.id, other_year)
        .join(hero, hero.id == Event.hero_attachment_id)
        .join(other, (other.sha256 == hero.sha256) & (other.event_id != Event.id))
        .join(other_event, other_event.id == other.event_id)
        .where(Event.id.in_(ids), other.retired_at.is_(None))
    )
    printed = await session.execute(
        select(Event.id, hero.dated_for)
        .join(hero, hero.id == Event.hero_attachment_id)
        .where(Event.id.in_(ids), hero.contains_date.is_(True), hero.dated_for.is_not(None))
    )
    by_id = {e.id: e for e in events}

    def own_year(event_id: UUID) -> int:
        event = by_id[event_id]
        return to_local(starts_at.get(event_id) or event.starts_at, event.tzid or DEFAULT_TZID).year

    reused = {i for i, year in shared.tuples() if int(year) != own_year(i)}
    reused |= {i for i, dated in printed.tuples() if dated and dated.year != own_year(i)}
    return reused


async def _checklist_counts(session: AsyncSession, ids: list[UUID]) -> dict[tuple[UUID, str], int]:
    rows = await session.execute(
        select(ChecklistItem.event_id, ChecklistItem.phase, func.count())
        .where(
            ChecklistItem.event_id.in_(ids),
            ChecklistItem.phase.in_(("planning", "followup")),
            ChecklistItem.required.is_(True),
            ChecklistItem.done_at.is_(None),
            ChecklistItem.waived_reason.is_(None),
        )
        .group_by(ChecklistItem.event_id, ChecklistItem.phase)
    )
    return {(event_id, phase): count for event_id, phase, count in rows.all()}


async def _retrospectives(session: AsyncSession, ids: list[UUID]) -> set[UUID]:
    rows = await session.scalars(
        select(Document.event_id).where(
            Document.event_id.in_(ids),
            Document.kind == "retrospective",
            func.btrim(Document.body_md) != "",
        )
    )
    return {i for i in rows if i is not None}


async def howto_presence(session: AsyncSession, events: Sequence[Event]) -> set[UUID]:
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


async def _profiles(session: AsyncSession, events: Sequence[Event]) -> dict[UUID, str]:
    category_ids = {e.primary_category_id for e in events if e.primary_category_id}
    if not category_ids:
        return {}
    rows = await session.execute(
        select(Category.id, Category.required_profile).where(Category.id.in_(category_ids))
    )
    by_category = dict(rows.all())
    return {e.id: by_category[e.primary_category_id] for e in events if e.primary_category_id}


async def load_guard_data(
    session: AsyncSession,
    events: Sequence[Event],
    *,
    starts_at: dict[UUID, datetime] | None = None,
) -> dict[UUID, GuardData]:
    """Read the guard inputs of `events`; `starts_at` carries starts that are about to apply."""
    ids = [e.id for e in events]
    if not ids:
        return {}
    open_root = (
        Comment.event_id.in_(ids),
        Comment.parent_id.is_(None),
        Comment.resolved_at.is_(None),
    )
    open_comments = await _counts(
        session,
        select(Comment.event_id, func.count()).where(*open_root).group_by(Comment.event_id),
    )
    hero_comments = {
        event_id: count
        for event_id, count in (await session.execute(_HERO_CHAIN, {"ids": ids})).all()
    }
    checklist = await _checklist_counts(session, ids)
    quarantined = await _counts(
        session,
        select(Attachment.event_id, func.count())
        .join(Event, Event.id == Attachment.event_id)
        .where(
            Attachment.event_id.in_(ids),
            Attachment.retired_at.is_(None),
            Attachment.scan_status.in_(("pending", "error")),
            (Attachment.kind.in_(("poster", "social_post"))) | (Attachment.visibility == "shared"),
            Attachment.id.is_distinct_from(Event.hero_attachment_id),
        )
        .group_by(Attachment.event_id),
    )
    reused = await _poster_reused(session, events, starts_at or {})
    retrospectives, howtos = (
        await _retrospectives(session, ids),
        await howto_presence(session, events),
    )
    profiles = await _profiles(session, events)
    return {
        i: GuardData(
            open_comments=open_comments.get(i, 0),
            open_hero_comments=hero_comments.get(i, 0),
            open_required_checklist=checklist.get((i, "planning"), 0),
            open_required_followup=checklist.get((i, "followup"), 0),
            quarantined_attachments=quarantined.get(i, 0),
            poster_reused=i in reused,
            retrospective_filled=i in retrospectives,
            howto_present=i in howtos,
            required_profile=profiles.get(i, "generic"),
        )
        for i in ids
    }
