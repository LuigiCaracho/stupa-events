"""Write the facts profile of a dossier (`PUT /events/{id}/facts`).

The profile follows the main category (`generic` without one). The body replaces the stored
facts; unknown keys of the profile are a 422. The same rule as for the other base data
applies (`events.editing`): `draft` with `event.edit`, `published` with `event.publish`, not in
the archive.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.rules import load_readable
from app.modules.events import facts, revisions
from app.modules.events.conflict import VersionConflict
from app.modules.events.editing import has_edit_right, locked_problem
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.modules.events.writer import update_event
from app.modules.taxonomy.models import Category
from app.shared.errors import FieldError, ForbiddenError, ValidationProblem


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
    if not has_edit_right(principal, event):
        raise ForbiddenError("Missing permission to edit this dossier")
    if event.state == EventState.ARCHIVED:
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
    await revisions.append_revision(session, updated, actor=principal.sub)
    await revisions.audit(session, updated, actor=principal.sub, action=AuditAction.EVENT_FACTS)
    return updated
