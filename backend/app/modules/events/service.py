"""Event service: create (T00), read, list and patch a dossier.

The service never commits; the router does. Every mutation writes a revision, an audit
entry and, for T00, a status event in the same transaction. Writes are optimistic:
`UPDATE ... WHERE rev = :rev` with a row count of 1, else 409 `conflict`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import revisions
from app.modules.events.access import load_visible, visible_events_query
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate, EventPatch
from app.modules.events.states import EDITABLE_STATES, EventState
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import bind, restricted_to_own
from app.modules.pipeline.guards import organization_scope_or_proposal
from app.modules.pipeline.snapshot import Snapshot, actor_of
from app.modules.taxonomy.models import Category
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.search import escape_like
from app.shared.timeutil import utcnow

CRITICAL_FIELDS = frozenset({"title", "starts_at", "ends_at", "venue_text", "primary_category_id"})
_NOT_NULL = ("title", "starts_at", "ends_at")


def _invalid(field: str, msg: str) -> ValidationProblem:
    return ValidationProblem("Invalid request.", errors=[FieldError(field=field, msg=msg)])


class EventService:
    """Create, read, list and patch dossiers for one request session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _organization(self, org_id: UUID) -> Organization:
        org = await self.session.get(Organization, org_id)
        if org is None or not org.active:
            raise NotFoundError("organization not found")
        return org

    async def _require_category(self, category_id: UUID | None) -> None:
        if category_id is None:
            return
        category = await self.session.get(Category, category_id)
        if category is None or not category.active:
            raise _invalid("primaryCategoryId", "unknown category")

    async def create(self, principal: Principal, body: EventCreate) -> Event:
        """Create a dossier in `idea` (T00).

        Raises:
            NotFoundError: The organization is unknown or outside the scope of the
                principal. Both look the same, so there is no existence oracle.
            ValidationProblem: The category is unknown.
        """
        await bind(self.session, principal)
        org = await self._organization(body.organization_id)
        scope_snapshot = Snapshot(
            state=EventState.IDEA,
            title=body.title,
            summary=body.summary,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            organization_id=org.id,
            primary_category_id=body.primary_category_id,
            venue_text=body.venue_text,
            created_by=principal.sub,
            submitted_by=None,
            poster=None,
            image_exception_reason=None,
        )
        if organization_scope_or_proposal(scope_snapshot, actor_of(principal, org.id), utcnow()):
            raise NotFoundError("organization not found")
        await self._require_category(body.primary_category_id)
        event = Event(
            state=EventState.IDEA.value,
            title=body.title,
            summary=body.summary,
            description_md=body.description_md,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            tzid=body.tzid,
            all_day=False,
            organization_id=org.id,
            venue_text=body.venue_text,
            primary_category_id=body.primary_category_id,
            created_by=principal.sub,
            rev=1,
            public_seq=0,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
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
            data={"organizationId": str(org.id)},
        )
        return event

    async def get(self, principal: Principal, event_id: UUID) -> Event:
        """Return an event the principal may read (404 otherwise)."""
        return await load_visible(self.session, principal, event_id)

    async def list_events(
        self,
        principal: Principal,
        *,
        state: str | None,
        organization_id: UUID | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Event], int]:
        """List the readable events by start time, filtered in SQL, with the total."""
        query = await visible_events_query(self.session, principal)
        if state is not None:
            query = query.where(Event.state == state)
        if organization_id is not None:
            query = query.where(Event.organization_id == organization_id)
        if q:
            pattern = f"%{escape_like(q.strip())}%"
            query = query.where(
                or_(
                    Event.title.ilike(pattern, escape="\\"),
                    Event.summary.ilike(pattern, escape="\\"),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = await self.session.scalars(
            query.order_by(Event.starts_at, Event.id).limit(limit).offset(offset)
        )
        return list(rows), total or 0

    def _authorize_edit(self, principal: Principal, event: Event) -> None:
        org_id = event.organization_id
        if org_id is None or not principal.has("event.edit", org_id):
            raise ForbiddenError("Missing permission: event.edit")
        if restricted_to_own(principal, org_id) and event.created_by != principal.sub:
            raise ForbiddenError("Only the creator may edit this dossier.")

    async def patch(self, principal: Principal, event_id: UUID, body: EventPatch) -> Event:
        """Change fields of a dossier in `idea` or `planning`.

        Raises:
            NotFoundError: No read right.
            ForbiddenError: No edit right, or a submitter on a dossier of someone else.
            ConflictError: `field_locked` outside `idea` and `planning`, `conflict` for a
                stale `rev`.
            ValidationProblem: Null for a required field, an end before the start, an
                unknown category.
        """
        event = await load_visible(self.session, principal, event_id)
        self._authorize_edit(principal, event)
        if event.state not in {s.value for s in EDITABLE_STATES}:
            raise ConflictError("Field is locked in this state.", code="field_locked")
        if body.rev != event.rev:
            raise ConflictError("The dossier was changed in the meantime.")
        changes = self._changes(body)
        starts = changes.get("starts_at", event.starts_at)
        ends = changes.get("ends_at", event.ends_at)
        if ends < starts:
            raise _invalid("endsAt", "endsAt must not be before startsAt")
        await self._require_category(changes.get("primary_category_id"))
        result = await self.session.execute(
            update(Event)
            .where(Event.id == event.id, Event.rev == body.rev)
            .values(**changes, rev=Event.rev + 1)
            .returning(Event)
            .execution_options(populate_existing=True, synchronize_session=False)
        )
        updated = result.scalar_one_or_none()
        if updated is None:
            raise ConflictError("The dossier was changed in the meantime.")
        field_class = "critical" if CRITICAL_FIELDS & changes.keys() else "text"
        await revisions.append_revision(
            self.session, updated, actor=principal.sub, field_class=field_class
        )
        await revisions.audit(
            self.session,
            updated,
            actor=principal.sub,
            action=AuditAction.EVENT_UPDATE,
            data={"fields": sorted(changes)},
        )
        return updated

    @staticmethod
    def _changes(body: EventPatch) -> dict[str, Any]:
        given = body.model_fields_set - {"rev"}
        changes: dict[str, Any] = {name: getattr(body, name) for name in given}
        changes.pop("all_day", None)
        for name in _NOT_NULL:
            if name in changes and changes[name] is None:
                raise _invalid(name, "must not be null")
        return changes
