"""Event service: create (T00, also as a proposal), read and patch a dossier.

The service never commits; the router does. Every mutation writes a revision and an audit
entry in the same transaction. Writes are optimistic: `UPDATE ... WHERE rev = :rev`, else
409 `conflict`. Which fields a person may change in which state is decided by the pure
`pipeline.fieldclass.plan_patch`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import allday, facts, revisions
from app.modules.events.access import guard_snapshot, load_visible, poster_of, snapshot_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import EditorDraft, Event
from app.modules.events.schemas import EventCreate, EventPatch
from app.modules.events.states import EventState
from app.modules.events.writer import update_event
from app.modules.media.ref_sync import add_refs, draft_owner_id, drop_draft_refs
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import bind
from app.modules.pipeline.actions import Committed
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.fieldclass import edit_right, plan_patch
from app.modules.pipeline.guards import organization_scope_or_proposal, proposal_quota
from app.modules.pipeline.livecheck import enforce_live
from app.modules.pipeline.snapshot import Snapshot
from app.modules.pipeline.transitions import ACTION_FEED_INVALIDATE
from app.modules.taxonomy.models import Category, Venue
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.timeutil import utcnow

DEFAULT_DURATION = timedelta(hours=2)
_NOT_NULL = ("title", "starts_at", "ends_at", "all_day")
_NON_FIELDS = {"rev", "note"}


def _invalid(field: str, msg: str, code: str | None = None) -> ValidationProblem:
    return ValidationProblem(
        "Invalid request.", code=code, errors=[FieldError(field=field, msg=msg)]
    )


def locked_problem(fields: tuple[str, ...]) -> ConflictError:
    """Build the 409 `field_locked` problem naming every locked field."""
    return ConflictError(
        "Field is locked in this state.",
        code="field_locked",
        errors=[FieldError(field=f, msg="locked in this state") for f in fields],
    )


async def derived_values(
    session: AsyncSession, event: Event, changes: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the columns that follow from a change: the location mark and the facts."""
    values: dict[str, Any] = {}
    if "venue_text" in changes:
        values |= {
            "location_precision": "hidden",
            "location_confirmed_at": None,
            "location_confirmed_by": None,
        }
    if "primary_category_id" in changes:
        category = (
            await session.get(Category, changes["primary_category_id"])
            if changes["primary_category_id"]
            else None
        )
        kept, dropped = facts.fit(category.required_profile if category else "generic", event.facts)
        if dropped:
            values["facts"] = kept
            session.info["facts_dropped"] = dropped
    return values


class EventService:
    """Create, read and patch dossiers for one request session."""

    def __init__(self, session: AsyncSession, *, editor_four_eyes: bool | None = None) -> None:
        self.session = session
        self.editor_four_eyes = editor_four_eyes

    async def _organization(self, org_id: UUID) -> Organization:
        org = await self.session.get(Organization, org_id)
        if org is None or not org.active:
            raise NotFoundError("organization not found")
        return org

    async def _require_references(self, category_id: UUID | None, venue_id: UUID | None) -> None:
        if category_id is not None:
            category = await self.session.get(Category, category_id)
            if category is None or not category.active:
                raise _invalid("primaryCategoryId", "unknown category")
        if venue_id is not None:
            venue = await self.session.get(Venue, venue_id)
            if venue is None or not venue.active:
                raise _invalid("venueId", "unknown venue", code="unknown_venue")

    async def _open_proposals(self, sub: str) -> int:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:sub))"), {"sub": sub}
        )
        count = await self.session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.state == EventState.IDEA.value,
                Event.organization_id.is_(None),
                Event.created_by == sub,
            )
        )
        return count or 0

    async def create(
        self, principal: Principal, body: EventCreate, *, format_id: UUID | None = None
    ) -> Event:
        """Create a dossier in `idea` (T00); without an organization it is a proposal.

        Raises:
            NotFoundError: The organization is unknown or outside the scope of the
                principal. Both look the same, so there is no existence oracle.
            ValidationProblem: Unknown category or venue, or `proposal_quota_exceeded`.
        """
        await bind(self.session, principal)
        org = await self._organization(body.organization_id) if body.organization_id else None
        org_id = org.id if org else None
        proposals = await self._open_proposals(principal.sub) if org is None else 0
        starts_at, ends_at, estimated = self._times_of(body)
        scope_snapshot = Snapshot(
            state=EventState.IDEA.value,
            title=body.title,
            summary=body.summary,
            starts_at=starts_at,
            ends_at=ends_at,
            organization_id=org_id,
            primary_category_id=body.primary_category_id,
            venue_text=body.venue_text,
            created_by=principal.sub,
            submitted_by=None,
            poster=None,
            image_exception_reason=None,
            open_proposals=proposals,
        )
        actor = actor_of(principal, org_id, self.editor_four_eyes)
        now = utcnow()
        if organization_scope_or_proposal(scope_snapshot, actor, now):
            raise NotFoundError("organization not found")
        if proposal_quota(scope_snapshot, actor, now):
            raise _invalid(
                "organizationId", "too many open proposals", code="proposal_quota_exceeded"
            )
        await self._require_references(body.primary_category_id, body.venue_id)
        event = Event(
            state=EventState.IDEA.value,
            title=body.title,
            summary=body.summary,
            description_md=body.description_md,
            starts_at=starts_at,
            ends_at=ends_at,
            end_estimated=estimated,
            tzid=body.tzid,
            all_day=body.all_day,
            starts_on=body.starts_on,
            ends_on=(body.ends_on or body.starts_on) if body.all_day else None,
            organization_id=org_id,
            venue_id=body.venue_id,
            venue_text=body.venue_text,
            primary_category_id=body.primary_category_id,
            format_id=format_id,
            cost_text=body.cost_text,
            ticket_url=body.ticket_url,
            website_url=body.website_url,
            created_by=principal.sub,
            rev=1,
            public_seq=0,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        await add_refs(self.session, "event", event.id, event.description_md)
        await revisions.append_revision(
            self.session, event, actor=principal.sub, field_class="state"
        )
        await revisions.append_status(
            self.session, event, transition_id="T00", from_state=None, actor=principal.sub
        )
        await revisions.audit(
            self.session,
            event,
            actor=principal.sub,
            action=AuditAction.EVENT_CREATE,
            data={"organizationId": str(org_id) if org_id else None},
        )
        return event

    @staticmethod
    def _times_of(body: EventCreate) -> tuple[datetime, datetime, bool]:
        if body.all_day:
            assert body.starts_on is not None
            start, end = allday.bounds(body.starts_on, body.ends_on or body.starts_on, body.tzid)
            return start, end, False
        assert body.starts_at is not None
        return (
            body.starts_at,
            body.ends_at or body.starts_at + DEFAULT_DURATION,
            body.ends_at is None,
        )

    async def get(self, principal: Principal, event_id: UUID) -> Event:
        """Return an event the principal may read (404 otherwise)."""
        return await load_visible(self.session, principal, event_id)

    async def check_edit(
        self, principal: Principal, event_id: UUID, expected_rev: int, changes: dict[str, Any]
    ):  # noqa: ANN201
        """Load the dossier and plan `changes` for the principal without writing.

        Returns:
            `(event, snapshot, actor, plan)`.

        Raises:
            NotFoundError: No read right.
            ForbiddenError: No edit right, or a submitter on a dossier of someone else.
            VersionConflict: `expected_rev` is stale.
            ConflictError: `field_locked` for any locked field (nothing is saved).
        """
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        poster = await poster_of(self.session, event)
        snapshot = snapshot_of(event, poster)
        actor = actor_of(principal, event.organization_id, self.editor_four_eyes)
        if not edit_right(snapshot, actor):
            raise ForbiddenError("Missing permission: event.edit")
        if expected_rev != event.rev:
            raise VersionConflict(event)
        plan = plan_patch(snapshot, actor, allday.resolve(event, changes))
        if plan.locked:
            raise locked_problem(plan.locked)
        return event, snapshot, actor, plan

    async def patch(
        self, principal: Principal, event_id: UUID, body: EventPatch, expected_rev: int
    ) -> tuple[Event, tuple[str, ...], Committed]:
        """Change fields of a dossier according to its state and the right of the caller.

        Returns:
            The event, the follow-up actions to run after the commit and their `Committed`.

        Raises:
            NotFoundError, ForbiddenError, VersionConflict, ConflictError: see `check_edit`.
            ValidationProblem: Null for a required field, an end before the start, an
                unknown category or venue, or a live guard refuses the result.
        """
        changes = self.changes_of(body)
        event, snapshot, actor, plan = await self.check_edit(
            principal, event_id, expected_rev, changes
        )
        if not plan.changes:
            await self._drop_draft(event, principal.sub)
            return event, (), await self._committed(event)
        starts = plan.changes.get("starts_at", event.starts_at)
        ends = plan.changes.get("ends_at", event.ends_at)
        if ends < starts:
            raise _invalid("endsAt", "endsAt must not be before startsAt")
        await self._require_references(
            plan.changes.get("primary_category_id"), plan.changes.get("venue_id")
        )
        if plan.live_guards:
            full = await guard_snapshot(
                self.session,
                event,
                await poster_of(self.session, event),
                starts_at=plan.changes.get("starts_at"),
            )
            enforce_live(replace(full, **plan.changes), actor, utcnow())
        values: dict[str, Any] = dict(plan.changes)
        if "ends_at" in values:
            values["end_estimated"] = False
        values |= await derived_values(self.session, event, plan.changes)
        if plan.bump_public_seq:
            values["public_seq"] = event.public_seq + 1
        updated = await update_event(self.session, event, values, states=[event.state])
        await revisions.append_revision(
            self.session,
            updated,
            actor=principal.sub,
            field_class=plan.field_class,
            note=body.note,
        )
        await revisions.audit(
            self.session,
            updated,
            actor=principal.sub,
            action=AuditAction.EVENT_UPDATE,
            data={"fields": sorted(plan.changes), "fieldClass": plan.field_class},
        )
        await self._drop_draft(updated, principal.sub)
        actions = (ACTION_FEED_INVALIDATE,) if updated.state == EventState.LIVE.value else ()
        return updated, actions, await self._committed(updated)

    async def _committed(self, event: Event) -> Committed:
        poster = await poster_of(self.session, event)
        return Committed(
            event.id, event.rev, poster.id if poster else None, bool(poster and poster.derivatives)
        )

    async def _drop_draft(self, event: Event, sub: str) -> None:
        await self.session.execute(
            delete(EditorDraft).where(
                EditorDraft.owner_kind == "event",
                EditorDraft.owner_id == event.id,
                EditorDraft.principal_sub == sub,
            )
        )
        await drop_draft_refs(self.session, draft_owner_id(event.id, sub))

    @staticmethod
    def changes_of(body: Any) -> dict[str, Any]:
        """Turn the given fields of a patch or draft body into column changes."""
        given = body.model_fields_set - _NON_FIELDS
        changes: dict[str, Any] = {name: getattr(body, name) for name in given}
        for name in _NOT_NULL:
            if name in changes and changes[name] is None:
                raise _invalid(name, "must not be null")
        return changes
