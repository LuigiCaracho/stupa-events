"""The task lists of `GET /tasks`: approvals, returned dossiers, own work, follow-up, changes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.events.access import snapshot_of, visible_events_query
from app.modules.events.card_schemas import EventCard, PersonRef
from app.modules.events.cards import present_cards
from app.modules.events.models import Event, EventRevision, EventStatusEvent
from app.modules.events.revision_views import list_revisions
from app.modules.orgs.scope import bind
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.decision import allowed_transitions
from app.modules.tasks.schemas import (
    AwaitingCard,
    ChangedCard,
    ChecklistTask,
    ReturnedCard,
    TaskCounts,
    TasksOut,
)

LIST_LIMIT = 50
OPEN_STATES = ("idea", "planning", "in_review", "approved")


def _card_dict(card: EventCard) -> dict:
    return {name: getattr(card, name) for name in EventCard.model_fields}


async def _events(session: AsyncSession, principal: Principal, *conditions) -> list[Event]:  # noqa: ANN002
    query = (await visible_events_query(session, principal)).where(*conditions)
    return list(await session.scalars(query.order_by(Event.starts_at, Event.id)))


def _rights(principal: Principal, event: Event, permission: str) -> bool:
    return principal.has(permission, event.organization_id)


async def _awaiting(
    session: AsyncSession, principal: Principal
) -> tuple[list[Event], dict[UUID, bool]]:
    found: list[Event] = []
    blocked: dict[UUID, bool] = {}
    for event in await _events(session, principal, Event.state == "in_review"):
        actor = actor_of(principal, event.organization_id)
        if "T04" in allowed_transitions(snapshot_of(event, None), actor):
            found.append(event)
            blocked[event.id] = actor.four_eyes and event.submitted_by == principal.sub
    return found, blocked


async def _returned(session: AsyncSession, principal: Principal):  # noqa: ANN202
    planning = (await visible_events_query(session, principal)).where(Event.state == "planning")
    latest = (
        select(EventStatusEvent)
        .distinct(EventStatusEvent.event_id)
        .where(EventStatusEvent.event_id.in_(select(planning.subquery().c.id)))
        .order_by(EventStatusEvent.event_id, EventStatusEvent.id.desc())
        .subquery()
    )
    last = aliased(EventStatusEvent, latest)
    rows = (
        await session.execute(
            select(Event, last)
            .join(last, last.event_id == Event.id)
            .where(last.transition_id == "T03")
            .order_by(Event.starts_at, Event.id)
        )
    ).all()
    return [(e, s) for e, s in rows if _rights(principal, e, "event.edit")]


async def _mine(session: AsyncSession, principal: Principal) -> list[Event]:
    await bind(session, principal)
    org_ids = {UUID(i) for slug, i in principal.org_ids.items() if slug in principal.org_roles}
    own = or_(Event.created_by == principal.sub, Event.submitted_by == principal.sub)
    where = or_(Event.organization_id.in_(org_ids), own) if org_ids else own
    return await _events(session, principal, Event.state.in_(OPEN_STATES), where)


async def _changed(session: AsyncSession, principal: Principal) -> list[tuple[Event, int]]:
    live = [
        e
        for e in await _events(session, principal, Event.state == "live")
        if _rights(principal, e, "event.edit_critical_live")
    ]
    if not live:
        return []
    base = {e.id: max(e.published_rev or 0, e.text_reviewed_rev) for e in live}
    changed_ids = set(
        await session.scalars(
            select(EventRevision.event_id)
            .where(
                EventRevision.event_id.in_(base),
                EventRevision.field_class == "text",
                EventRevision.actor_id != principal.sub,
                EventRevision.rev > _baseline(base),
            )
            .distinct()
        )
    )
    return [(e, base[e.id]) for e in live if e.id in changed_ids]


def _baseline(base: dict[UUID, int]):  # noqa: ANN202
    return case(*((EventRevision.event_id == k, v) for k, v in base.items()), else_=0)


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all()) if subs else {}


async def _checklist_tasks(session: AsyncSession, principal: Principal) -> list[ChecklistTask]:
    """Open checklist items assigned to the caller in dossiers the caller reads."""
    visible = (await visible_events_query(session, principal)).subquery()
    rows = await session.execute(
        select(ChecklistItem, visible.c.title)
        .join(visible, visible.c.id == ChecklistItem.event_id)
        .where(
            ChecklistItem.assignee_sub == principal.sub,
            ChecklistItem.done_at.is_(None),
            ChecklistItem.waived_reason.is_(None),
        )
        .order_by(ChecklistItem.due_at.asc().nulls_last(), ChecklistItem.created_at)
        .limit(LIST_LIMIT)
    )
    return [
        ChecklistTask(
            id=item.id,
            event_id=item.event_id,
            event_title=title,
            text=item.text,
            phase=item.phase,
            due_at=item.due_at,
        )
        for item, title in rows.all()
    ]


async def build_tasks(session: AsyncSession, principal: Principal) -> TasksOut:
    """Compute the task lists of the caller; each list holds at most 50 cards."""
    await bind(session, principal)
    awaiting, blocked = await _awaiting(session, principal)
    returned = await _returned(session, principal)
    mine = await _mine(session, principal)
    followup = [
        e
        for e in await _events(session, principal, Event.state == "followup")
        if _rights(principal, e, "event.submit")
    ]
    changed = await _changed(session, principal)
    checklist_items = await _checklist_tasks(session, principal)
    names = await _names(session, {s.actor_id for _, s in returned if s.actor_id})

    async def cards(events: list[Event]) -> list[EventCard]:
        return await present_cards(session, principal, events[:LIST_LIMIT])

    changed_cards = []
    for card, (event, base) in zip(
        await cards([e for e, _ in changed]), changed[:LIST_LIMIT], strict=True
    ):
        items, _ = await list_revisions(
            session,
            principal,
            event.id,
            field_class="text",
            limit=LIST_LIMIT,
            offset=0,
            min_rev=base,
        )
        changed_cards.append(
            ChangedCard(
                **_card_dict(card),
                baseline_rev=base,
                changes=items,
            )
        )
    return TasksOut(
        awaiting_review=[
            AwaitingCard(**_card_dict(c), four_eyes_blocked=blocked[c.id])
            for c in await cards(awaiting)
        ],
        returned=[
            ReturnedCard(
                **_card_dict(card),
                note=status.note,
                returned_at=status.at,
                returned_by=PersonRef(
                    sub=status.actor_id or "", display_name=names.get(status.actor_id or "")
                ),
            )
            for card, (_, status) in zip(
                await cards([e for e, _ in returned]), returned[:LIST_LIMIT], strict=True
            )
        ],
        due=[],
        mine=await cards(mine),
        followup_open=await cards(followup),
        changed_after_publish=changed_cards,
        checklist_items=checklist_items,
        counts=TaskCounts(
            awaiting_review=len(awaiting),
            returned=len(returned),
            due=0,
            mine=len(mine),
            followup_open=len(followup),
            changed_after_publish=len(changed),
            checklist_items=len(checklist_items),
        ),
    )
