"""Pipeline service: `fire` is the only write path onto `event.state` (PLAN 4.5).

`stage_fire` evaluates the transition, writes the new state with an optimistic
`UPDATE ... WHERE state = :from AND rev = :rev`, then the revision, the status event and
the audit entry in the same transaction. It does not commit; the router commits and then
runs the actions. The database trigger `enforce_publish_image` is the net below the guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import revisions
from app.modules.events.access import load_visible, poster_of, snapshot_of
from app.modules.events.models import Event
from app.modules.orgs.scope import bind
from app.modules.pipeline import slugs
from app.modules.pipeline.actions import Committed
from app.modules.pipeline.reasons import Reason, blocker, blockers
from app.modules.pipeline.snapshot import actor_of
from app.modules.pipeline.transitions import (
    TRANSITIONS,
    Transition,
    Verdict,
    decide,
)
from app.shared.errors import ConflictError, ForbiddenError, ValidationProblem
from app.shared.timeutil import utcnow

CHECK_VIOLATION = "23514"
PUBLISH_IMAGE_TRIGGER_MARKER = "without a valid poster or image exception"


@dataclass(frozen=True, slots=True)
class GuardReport:
    """The answer of `GET /events/{id}/guards/{transition}`."""

    transition: str
    allowed: bool
    reasons: list[Reason]


@dataclass(frozen=True, slots=True)
class Fired:
    """Result of `stage_fire`: the changed event and what to run after the commit."""

    event: Event
    actions: tuple[str, ...]
    committed: Committed


def refusal(reasons: list[Reason]) -> ValidationProblem:
    """Build the 422 problem for blocking reasons: its code is the first blocker's code."""
    first = blockers(reasons)[0]
    return ValidationProblem(
        "The transition is not allowed yet.",
        code=first.code,
        extensions={
            "reasons": [
                {
                    "code": r.code,
                    "field": r.field,
                    "severity": r.severity.value,
                    "messageKey": r.message_key,
                    "fixAction": r.fix_action.value if r.fix_action else None,
                }
                for r in reasons
            ]
        },
    )


def _report_reasons(verdict: Verdict) -> list[Reason]:
    match verdict.outcome:
        case "forbidden" | "invalid_transition":
            return [blocker(verdict.outcome)]
        case _:
            return list(verdict.reasons)


def _transition(transition_id: str) -> Transition:
    return TRANSITIONS[transition_id]


class PipelineService:
    """Evaluate and fire transitions for one request session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def guards(
        self, principal: Principal, event_id: UUID, transition_id: str, now: datetime | None = None
    ) -> GuardReport:
        """Compute the guard list for a transition without storing anything."""
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        poster = await poster_of(self.session, event)
        snapshot = snapshot_of(event, poster)
        actor = actor_of(principal, event.organization_id)
        moment = now or utcnow()
        transition = _transition(transition_id)
        verdict = decide(transition, snapshot, actor, moment)
        return GuardReport(transition_id, verdict.outcome == "ok", _report_reasons(verdict))

    async def stage_fire(
        self,
        principal: Principal,
        event_id: UUID,
        transition_id: str,
        *,
        note: str | None = None,
        now: datetime | None = None,
    ) -> Fired:
        """Fire a transition inside the open transaction.

        Raises:
            NotFoundError: No read right on the event.
            ForbiddenError: The role may not fire this transition.
            ConflictError: `invalid_transition` in the current state, or `conflict` when
                the dossier changed between the read and the write.
            ValidationProblem: A guard refuses; the code is the first blocker's code.
        """
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        poster = await poster_of(self.session, event)
        moment = now or utcnow()
        transition = _transition(transition_id)
        verdict = decide(
            transition,
            snapshot_of(event, poster),
            actor_of(principal, event.organization_id),
            moment,
        )
        self._raise_unless_ok(verdict, transition)
        values = await self._values(transition, event, principal)
        updated = await self._write(event, transition, values)
        await revisions.append_revision(
            self.session, updated, actor=principal.sub, field_class="state", note=note
        )
        await revisions.append_status(
            self.session,
            updated,
            transition_id=transition.id,
            from_state=transition.source.value,
            actor=principal.sub,
            note=note,
        )
        await revisions.audit(
            self.session,
            updated,
            actor=principal.sub,
            action=AuditAction.EVENT_TRANSITION,
            data={
                "transition": transition.id,
                "from": transition.source.value,
                "to": transition.target.value,
            },
        )
        return Fired(
            updated,
            transition.actions,
            Committed(
                event_id=updated.id,
                rev=updated.rev,
                poster_id=poster.id if poster else None,
                poster_has_derivatives=bool(poster and poster.derivatives),
            ),
        )

    @staticmethod
    def _raise_unless_ok(verdict: Verdict, transition: Transition) -> None:
        match verdict.outcome:
            case "forbidden":
                raise ForbiddenError(f"Missing permission: {transition.permission}")
            case "invalid_transition":
                raise ConflictError(
                    f"{transition.id} is not defined in this state.", code="invalid_transition"
                )
            case "blocked":
                raise refusal(list(verdict.reasons))
            case _:
                return

    async def _values(
        self, transition: Transition, event: Event, principal: Principal
    ) -> dict[str, Any]:
        values: dict[str, Any] = {"state": transition.target.value}
        if "submitted_by" in transition.sets:
            values["submitted_by"] = principal.sub
        if "approved_by" in transition.sets:
            values["approved_by"] = principal.sub
        if "public_seq" in transition.sets:
            values["public_seq"] = event.public_seq + 1
        if "slug" in transition.sets:
            base = slugs.base_slug(event.title, event.starts_at, event.tzid)
            values["slug"] = await slugs.unique_slug(self.session, base)
        return values

    async def _write(self, event: Event, transition: Transition, values: dict[str, Any]) -> Event:
        try:
            result = await self.session.execute(
                update(Event)
                .where(
                    Event.id == event.id,
                    Event.state == transition.source.value,
                    Event.rev == event.rev,
                )
                .values(**values, rev=Event.rev + 1)
                .returning(Event)
                .execution_options(populate_existing=True, synchronize_session=False)
            )
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            if code == CHECK_VIOLATION and PUBLISH_IMAGE_TRIGGER_MARKER in str(exc.orig):
                raise refusal([blocker("image_required", field="poster")]) from exc
            raise
        updated = result.scalar_one_or_none()
        if updated is None:
            raise ConflictError("The dossier was changed in the meantime.")
        return updated
