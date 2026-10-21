"""Write the facts profile of a dossier (`PUT /events/{id}/facts`).

The profile follows the main category (`generic` without one). The body replaces the stored
facts; unknown keys of the profile are a 422. The same state rule as for the text fields
applies: open in `idea`, `planning` and `live`, in `in_review` only with `event.approve`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.rules import ensure_permission, load_readable
from app.modules.events import facts, revisions
from app.modules.events.access import snapshot_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event
from app.modules.events.service import locked_problem
from app.modules.events.writer import update_event
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.fieldclass import text_locked
from app.modules.taxonomy.models import Category
from app.shared.errors import FieldError, ValidationProblem


async def put_facts(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    raw: dict[str, Any],
    expected_rev: int,
) -> Event:
    """Validate `raw` against the profile of the category and store it (no commit).

    Raises:
        NotFoundError, ForbiddenError, VersionConflict: as for every dossier write.
        ConflictError: `field_locked` in a state or for a role that may not edit text.
        ValidationProblem: A key is unknown to the profile or a value is invalid.
    """
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.edit")
    actor = actor_of(principal, event.organization_id)
    if text_locked(snapshot_of(event, None), actor):
        raise locked_problem(("facts",))
    if expected_rev != event.rev:
        raise VersionConflict(event)
    category = (
        await session.get(Category, event.primary_category_id)
        if event.primary_category_id
        else None
    )
    try:
        stored = facts.parse(category.required_profile if category else "generic", raw)
    except ValidationError as exc:
        raise ValidationProblem(
            "Invalid facts.",
            errors=[
                FieldError(field=f"facts.{name}", msg=msg)
                for name, msg in facts.validation_errors(exc)
            ],
        ) from exc
    updated = await update_event(session, event, {"facts": stored}, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub, field_class="dossier")
    await revisions.audit(session, updated, actor=principal.sub, action=AuditAction.EVENT_FACTS)
    return updated
