"""Event service: create, read and patch a dossier.

The service never commits; the router does. Every mutation writes a revision and an audit
entry in the same transaction. Writes are optimistic: `UPDATE ... WHERE rev = :rev`, else
409 `conflict`. Who may change which fields in which state is decided by `events.editing`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import allday, facts, revisions
from app.modules.events.access import load_visible, poster_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.editing import (
    API_NAMES,
    bumps_public_seq,
    has_edit_right,
    locked_problem,
)
from app.modules.events.lifecycle import EDITOR_RIGHT
from app.modules.events.models import EditorDraft, Event
from app.modules.events.postcommit import ACTION_FEED_INVALIDATE, Committed
from app.modules.events.schemas import EventCreate, EventPatch
from app.modules.events.states import EventState
from app.modules.events.step import committed_of
from app.modules.events.writer import update_event
from app.modules.media.ref_sync import add_refs, draft_owner_id, drop_draft_refs
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import bind
from app.modules.taxonomy.models import Category, Venue
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)

DEFAULT_DURATION = timedelta(hours=2)
_NOT_NULL = ("title", "starts_at", "ends_at", "all_day")
_NON_FIELDS = {"rev", "note"}


def _invalid(field: str, msg: str, code: str | None = None) -> ValidationProblem:
    return ValidationProblem(
        "Invalid request.", code=code, errors=[FieldError(field=field, msg=msg)]
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


def effective_changes(event: Event, changes: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the requested column values that differ from the stored ones."""
    return {name: value for name, value in changes.items() if getattr(event, name) != value}


class EventService:
    """Create, read and patch dossiers for one request session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def create(
        self,
        principal: Principal,
        body: EventCreate,
        *,
        format_id: UUID | None = None,
        origin_kind: str = "internal",
    ) -> Event:
        """Create a draft in an organization where the principal holds `event.create`.

        Raises:
            NotFoundError: The organization is unknown or outside the scope of the
                principal. Both look the same, so there is no existence oracle.
            ValidationProblem: Unknown category or venue.
        """
        await bind(self.session, principal)
        org = await self._organization(body.organization_id)
        if not principal.has("event.create", org.id):
            raise NotFoundError("organization not found")
        await self._require_references(body.primary_category_id, body.venue_id)
        event = self._build(
            body,
            org,
            actor=principal.sub,
            state=EventState.DRAFT,
            origin_kind=origin_kind,
            format_id=format_id,
        )
        return await self._persist(event, actor=principal.sub, actor_type="human", note=None)

    async def create_imported(
        self,
        actor_sub: str,
        body: EventCreate,
        *,
        origin_kind: str,
        state: EventState = EventState.DRAFT,
        note: str | None = None,
    ) -> Event:
        """Create a dossier for the import pipeline with the system as the actor.

        The caller has checked the right (`import.review`, `import.legacy`) and the scope;
        the dossier keeps `published_at` empty, so an archived one never reaches the feed.

        Raises:
            NotFoundError: The organization is unknown or inactive.
            ValidationProblem: Unknown category or venue.
        """
        org = await self._organization(body.organization_id)
        await self._require_references(body.primary_category_id, body.venue_id)
        event = self._build(body, org, actor=actor_sub, state=state, origin_kind=origin_kind)
        return await self._persist(event, actor=actor_sub, actor_type="system", note=note)

    def _build(
        self,
        body: EventCreate,
        org: Organization,
        *,
        actor: str,
        state: EventState,
        origin_kind: str,
        format_id: UUID | None = None,
    ) -> Event:
        starts_at, ends_at, estimated = self._times_of(body)
        return Event(
            state=state.value,
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
            organization_id=org.id,
            venue_id=body.venue_id,
            venue_text=body.venue_text,
            primary_category_id=body.primary_category_id,
            format_id=format_id,
            cost_text=body.cost_text,
            ticket_url=body.ticket_url,
            website_url=body.website_url,
            origin_kind=origin_kind,
            created_by=actor,
            rev=1,
            public_seq=0,
        )

    async def _persist(
        self, event: Event, *, actor: str, actor_type: str, note: str | None
    ) -> Event:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        await add_refs(self.session, "event", event.id, event.description_md)
        await revisions.append_revision(
            self.session, event, actor=actor, note=note, actor_type=actor_type
        )
        await revisions.append_status(
            self.session,
            event,
            transition_id="create",
            from_state=None,
            actor=actor,
            note=note,
            actor_type=actor_type,
        )
        await revisions.audit(
            self.session,
            event,
            actor=actor,
            action=AuditAction.EVENT_CREATE,
            data={"organizationId": str(event.organization_id), "originKind": event.origin_kind},
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
    ) -> tuple[Event, dict[str, Any]]:
        """Load the dossier and check the right, the version and the state for `changes`.

        Returns:
            The event and the effective changes (values that differ from the stored ones).

        Raises:
            NotFoundError: No read right.
            ForbiddenError: No right to edit, or a submitter on a dossier of someone else.
            VersionConflict: `expected_rev` is stale.
            ConflictError: `field_locked` for every field of a changed archived dossier.
        """
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        if not has_edit_right(principal, event):
            raise ForbiddenError("Missing permission to edit this dossier")
        if expected_rev != event.rev:
            raise VersionConflict(event)
        effective = effective_changes(event, allday.resolve(event, changes))
        if effective and event.state == EventState.ARCHIVED:
            raise locked_problem(tuple(API_NAMES.get(name, name) for name in effective))
        return event, effective

    async def patch(
        self, principal: Principal, event_id: UUID, body: EventPatch, expected_rev: int
    ) -> tuple[Event, tuple[str, ...], Committed]:
        """Change fields of a dossier according to its state and the right of the caller.

        Returns:
            The event, the follow-up actions to run after the commit and their `Committed`.

        Raises:
            NotFoundError, ForbiddenError, VersionConflict, ConflictError: see `check_edit`.
            ValidationProblem: Null for a required field, an end before the start, or an
                unknown category or venue.
        """
        changes = self.changes_of(body)
        assigned = changes.pop("organization_id", None)
        event, effective = await self.check_edit(principal, event_id, expected_rev, changes)
        if assigned is not None:
            effective["organization_id"] = await self._assign(principal, event, assigned)
        if not effective:
            await self._drop_draft(event, principal.sub)
            return event, (), await self._committed(event)
        starts = effective.get("starts_at", event.starts_at)
        ends = effective.get("ends_at", event.ends_at)
        if ends < starts:
            raise _invalid("endsAt", "endsAt must not be before startsAt")
        await self._require_references(
            effective.get("primary_category_id"), effective.get("venue_id")
        )
        values: dict[str, Any] = dict(effective)
        if "ends_at" in values:
            values["end_estimated"] = False
        values |= await derived_values(self.session, event, effective)
        if bumps_public_seq(event, effective):
            values["public_seq"] = event.public_seq + 1
        updated = await update_event(self.session, event, values, states=[event.state])
        await revisions.append_revision(self.session, updated, actor=principal.sub, note=body.note)
        await revisions.audit(
            self.session,
            updated,
            actor=principal.sub,
            action=AuditAction.EVENT_UPDATE,
            data={"fields": sorted(effective)},
        )
        await self._drop_draft(updated, principal.sub)
        actions = (ACTION_FEED_INVALIDATE,) if updated.state == EventState.PUBLISHED else ()
        return updated, actions, await self._committed(updated)

    async def _assign(self, principal: Principal, event: Event, org_id: UUID) -> UUID:
        if not principal.has(EDITOR_RIGHT):
            raise ForbiddenError("Only the editorial team assigns an organization.")
        if event.organization_id is not None:
            raise ConflictError("The organization is set already.", code="field_locked")
        return (await self._organization(org_id)).id

    async def _committed(self, event: Event) -> Committed:
        return committed_of(event, await poster_of(self.session, event))

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
