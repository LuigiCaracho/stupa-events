"""Version conflicts: the 409 with the current dossier, and the ETag helpers (contract 4.2)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.shared.errors import (
    ConflictError,
    FieldError,
    PreconditionRequiredError,
    ValidationProblem,
)

CONFLICT_MESSAGE = "The dossier was changed in the meantime."


class VersionConflict(ConflictError):
    """The dossier changed since the caller read it; carries the current row."""

    def __init__(self, event: Event) -> None:
        super().__init__(CONFLICT_MESSAGE, code="conflict", extensions={"currentRev": event.rev})
        self.event = event


def etag_of(rev: int) -> str:
    """Return the strong ETag of a revision."""
    return f'"{rev}"'


def set_etag(response: Response, rev: int) -> None:
    """Put the ETag of the dossier revision on the response."""
    response.headers["ETag"] = etag_of(rev)


def parse_if_match(header: str | None) -> int | None:
    """Read the revision out of an `If-Match` header; `None` when absent or `*`.

    Raises:
        ValidationProblem: The header is not a quoted revision number.
    """
    if header is None or header.strip() == "*":
        return None
    value = header.strip().removeprefix("W/").strip('"')
    if not value.isdigit() or int(value) < 1:
        raise ValidationProblem(
            "Invalid If-Match header.",
            errors=[FieldError(field="If-Match", msg="expected a revision")],
        )
    return int(value)


def revision_of(header: str | None, body_rev: int | None) -> int:
    """Pick the expected revision: the header, else the body `rev`.

    Raises:
        PreconditionRequiredError: Neither is given.
        ValidationProblem: Both are given and differ, or the header is malformed.
    """
    from_header = parse_if_match(header)
    if from_header is not None and body_rev is not None and from_header != body_rev:
        raise ValidationProblem(
            "If-Match and rev differ.",
            errors=[FieldError(field="rev", msg="differs from If-Match")],
        )
    expected = from_header if from_header is not None else body_rev
    if expected is None:
        raise PreconditionRequiredError("An If-Match header or a rev is required.")
    return expected


@asynccontextmanager
async def with_current(session: AsyncSession, principal: Principal) -> AsyncIterator[None]:
    """Add the current `EventOut` to a `VersionConflict` raised inside the block."""
    from app.modules.events.presenter import present

    try:
        yield
    except VersionConflict as exc:
        current: dict[str, Any] = (await present(session, principal, [exc.event]))[0].model_dump(
            mode="json", by_alias=True
        )
        assert exc.extensions is not None
        exc.extensions["current"] = current
        raise


def require_if_match(header: str | None) -> int:
    """Return the `If-Match` revision of a decision that must see what it decides on.

    Raises:
        PreconditionRequiredError: The header is missing.
        ValidationProblem: The header is malformed.
    """
    expected = parse_if_match(header)
    if expected is None:
        raise PreconditionRequiredError("An If-Match header is required.")
    return expected
