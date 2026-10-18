"""Pipeline service: `fire` is the only write path onto `event.state` (PLAN 4.5).

`stage_fire` evaluates the transition with `decide`, writes the new state with an
optimistic `UPDATE ... WHERE state = :from AND rev = :rev`, then the revision, the status
event and the audit entry in the same transaction. It does not commit; the router commits
and then runs the actions. `stage_system_fire` is the same path for the worker, with the
system actor. The triggers `enforce_publish_image` and the Four-Eyes CHECK are the nets
below the guards.
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
from app.modules.events.access import guard_snapshot, load_visible, poster_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event
from app.modules.orgs.scope import bind
from app.modules.pipeline import slugs
from app.modules.pipeline.actions import Committed
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.decision import Verdict, decide
from app.modules.pipeline.reasons import Reason, blocker, payload, refusal
from app.modules.pipeline.snapshot import SYSTEM_ACTOR, Actor, Snapshot
from app.modules.pipeline.transitions import TRANSITIONS, Transition
from app.modules.pipeline.values import transition_values
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.timeutil import utcnow

CHECK_VIOLATION = "23514"
PUBLISH_IMAGE_TRIGGER_MARKER = "without a valid poster or image exception"
FOUR_EYES_CONSTRAINT = "ck_event_status_event_four_eyes"


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


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def four_eyes_refusal(reasons: list[Reason]) -> ForbiddenError:
    """Build the 403 `four_eyes` problem with its `reasons[]`."""
    return ForbiddenError(
        "The approving person must not be the submitting person.",
        code="four_eyes",
        extensions={"reasons": payload(reasons or [blocker("four_eyes")])},
    )


def _report_reasons(verdict: Verdict) -> list[Reason]:
    match verdict.outcome:
        case "forbidden" | "invalid_transition" | "reason_required":
            return [blocker(verdict.outcome)]
        case _:
            return list(verdict.reasons)


def _reload_conflict(event: Event) -> VersionConflict:
    return VersionConflict(event)


class PipelineService:
    """Evaluate and fire transitions for one request session."""

    def __init__(self, session: AsyncSession, *, editor_four_eyes: bool | None = None) -> None:
        self.session = session
        self.editor_four_eyes = editor_four_eyes

    async def guards(
        self,
        principal: Principal,
        event_id: UUID,
        transition_id: str,
        now: datetime | None = None,
    ) -> GuardReport:
        """Compute the guard list for a transition without storing anything."""
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        poster = await poster_of(self.session, event)
        snapshot = await guard_snapshot(self.session, event, poster)
        actor = actor_of(principal, event.organization_id, self.editor_four_eyes)
        verdict = decide(TRANSITIONS[transition_id], snapshot, actor, now or utcnow())
        return GuardReport(transition_id, verdict.outcome == "ok", _report_reasons(verdict))

    async def stage_fire(
        self,
        principal: Principal,
        event_id: UUID,
        transition_id: str,
        *,
        note: str | None = None,
        publish_at: datetime | None = None,
        expected_rev: int | None = None,
        now: datetime | None = None,
    ) -> Fired:
        """Fire a transition inside the open transaction.

        Raises:
            NotFoundError: No read right on the event.
            ForbiddenError: The role may not fire this transition, or `four_eyes`.
            ConflictError: `invalid_transition` in the current state, or `conflict` when
                the dossier changed (a `VersionConflict`).
            ValidationProblem: A guard refuses (the code of the first blocker),
                `reason_required`, `publish_at_in_past`, `publish_after_end`.
        """
        event = await load_visible(self.session, principal, event_id)
        await bind(self.session, principal)
        actor = actor_of(principal, event.organization_id, self.editor_four_eyes)
        return await self._fire(event, actor, transition_id, note, publish_at, expected_rev, now)

    async def stage_system_fire(
        self, event_id: UUID, transition_id: str, now: datetime | None = None
    ) -> Fired:
        """Fire a transition as the worker: same `decide`, the system actor, no read scope."""
        event = await self.session.get(Event, event_id)
        if event is None:
            raise NotFoundError("event not found")
        return await self._fire(event, SYSTEM_ACTOR, transition_id, None, None, None, now)

    async def _fire(
        self,
        event: Event,
        actor: Actor,
        transition_id: str,
        note: str | None,
        publish_at: datetime | None,
        expected_rev: int | None,
        now: datetime | None,
    ) -> Fired:
        moment = now or utcnow()
        transition = TRANSITIONS[transition_id]
        if expected_rev is not None and expected_rev != event.rev:
            raise _reload_conflict(event)
        poster = await poster_of(self.session, event)
        snapshot = await guard_snapshot(self.session, event, poster)
        note = (note or "").strip() or None
        verdict = decide(transition, snapshot, actor, moment, note_given=note is not None)
        if verdict.outcome in {"forbidden", "invalid_transition"}:
            self._raise_unless_ok(verdict, transition, snapshot)
        self._check_publish_at(transition, publish_at, snapshot, moment)
        self._raise_unless_ok(verdict, transition, snapshot)
        values = await self._values(transition, event, actor, publish_at)
        updated = await self._write(event, transition, values)
        await self._record(updated, transition, actor, snapshot, note)
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

    async def _record(
        self,
        updated: Event,
        transition: Transition,
        actor: Actor,
        snapshot: Snapshot,
        note: str | None,
    ) -> None:
        actor_type = "system" if actor.kind == "system" else "human"
        await revisions.append_revision(
            self.session,
            updated,
            actor=actor.sub,
            field_class="state",
            note=note,
            actor_type=actor_type,
        )
        try:
            await revisions.append_status(
                self.session,
                updated,
                transition_id=transition.id,
                from_state=snapshot.state,
                actor=actor.sub,
                note=note,
                actor_type=actor_type,
                four_eyes=actor.four_eyes and transition.four_eyes,
                submitted_by=snapshot.submitted_by,
            )
        except DBAPIError as exc:
            if _sqlstate(exc) == CHECK_VIOLATION and FOUR_EYES_CONSTRAINT in str(exc.orig):
                raise four_eyes_refusal([]) from exc
            raise
        data: dict[str, Any] = {
            "transition": transition.id,
            "from": snapshot.state,
            "to": transition.target.value,
        }
        if transition.four_eyes and snapshot.submitted_by == actor.sub:
            data["selfApproved"] = True
        await revisions.audit(
            self.session,
            updated,
            actor=actor.sub,
            action=AuditAction.EVENT_TRANSITION,
            data=data,
        )

    @staticmethod
    def _check_publish_at(
        transition: Transition, publish_at: datetime | None, snapshot: Snapshot, now: datetime
    ) -> None:
        if publish_at is None:
            return
        if transition.id != "T04":
            raise ValidationProblem(
                "publishAt applies to T04 only.",
                errors=[FieldError(field="publishAt", msg="not allowed for this transition")],
            )
        if publish_at <= now:
            raise ValidationProblem(
                "publishAt must lie in the future.",
                code="publish_at_in_past",
                errors=[FieldError(field="publishAt", msg="must be in the future")],
            )
        if snapshot.ends_at is not None and publish_at >= snapshot.ends_at:
            raise ValidationProblem(
                "publishAt must lie before the end.",
                code="publish_after_end",
                errors=[FieldError(field="publishAt", msg="must be before the end")],
            )

    @staticmethod
    def _raise_unless_ok(verdict: Verdict, transition: Transition, snapshot: Snapshot) -> None:
        match verdict.outcome:
            case "forbidden":
                raise ForbiddenError(
                    f"Missing permission: {transition.permission or 'system only'}"
                )
            case "invalid_transition":
                raise ConflictError(
                    f"{transition.id} is not defined in this state.", code="invalid_transition"
                )
            case "reason_required":
                raise ValidationProblem(
                    "A note is required.",
                    code="reason_required",
                    errors=[FieldError(field="note", msg="required")],
                )
            case "four_eyes":
                raise four_eyes_refusal(list(verdict.reasons))
            case "blocked":
                raise refusal(list(verdict.reasons))
            case _:
                return

    async def _values(
        self, transition: Transition, event: Event, actor: Actor, publish_at: datetime | None
    ) -> dict[str, Any]:
        slug = None
        if any(rule == "slug" for _, rule in transition.sets):
            base = slugs.base_slug(event.title, event.starts_at, event.tzid)
            slug = await slugs.unique_slug(self.session, base)
        return transition_values(
            transition,
            actor_sub=actor.sub,
            rev=event.rev,
            public_seq=event.public_seq,
            publish_at=publish_at,
            slug=slug,
        )

    async def _write(self, event: Event, transition: Transition, values: dict[str, Any]) -> Event:
        try:
            result = await self.session.execute(
                update(Event)
                .where(
                    Event.id == event.id,
                    Event.state.in_([s.value for s in transition.source]),
                    Event.rev == event.rev,
                )
                .values(**values, rev=Event.rev + 1)
                .returning(Event)
                .execution_options(populate_existing=True, synchronize_session=False)
            )
        except DBAPIError as exc:
            if _sqlstate(exc) == CHECK_VIOLATION and PUBLISH_IMAGE_TRIGGER_MARKER in str(exc.orig):
                raise refusal([blocker("image_required", field="poster")]) from exc
            raise
        updated = result.scalar_one_or_none()
        if updated is None:
            await self.session.refresh(event)
            raise _reload_conflict(event)
        return updated
