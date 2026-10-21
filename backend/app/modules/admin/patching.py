"""Helpers shared by the taxonomy routers: partial updates and the config audit entry.

A `PATCH` body names only the fields it changes (`model_fields_set`). A field that the
column cannot hold as `NULL` is refused with a 422 when the body sets it to `null`.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.schemas import CamelModel
from app.modules.pipeline.actions import invalidate_public
from app.shared.errors import ConflictError, FieldError, ValidationProblem


def changes(body: CamelModel, nullable: frozenset[str]) -> dict[str, Any]:
    """Return `{field: value}` of the fields the body sets.

    Raises:
        ValidationProblem: A field outside `nullable` is set to `null`.
    """
    values = {name: getattr(body, name) for name in body.model_fields_set}
    bad = [name for name, value in values.items() if value is None and name not in nullable]
    if bad:
        raise ValidationProblem(
            "Invalid request.",
            errors=[FieldError(field=to_camel(name), msg="must not be null") for name in bad],
        )
    return values


def slug_taken() -> ConflictError:
    """Return the 409 for a slug that exists already."""
    return ConflictError("The slug is taken.", code="slug_taken")


def invalid(field: str, msg: str, code: str = "validation_error") -> ValidationProblem:
    """Return a 422 for one field."""
    return ValidationProblem(
        "Invalid request.", code=code, errors=[FieldError(field=field, msg=msg)]
    )


async def audit_config(
    db: AsyncSession, actor: str, target_type: str, target_id: object, fields: list[str]
) -> None:
    """Write a `CONFIG_CHANGE` entry that names the changed fields, never their values."""
    await audit_record(
        db,
        actor=actor,
        action=AuditAction.CONFIG_CHANGE,
        target_type=target_type,
        target_id=str(target_id),
        data={"fields": sorted(to_camel(name) for name in fields)},
    )


async def invalidate_feed(request: Request) -> None:
    """Mark the public feed and calendars stale after a taxonomy edit that the view shows."""
    await invalidate_public(getattr(request.app.state, "arq_pool", None))
