"""The opaque feed cursor: `base64url` over `{startsAt, id}` (contract 9.2)."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.publicapi.clock import representable
from app.shared.errors import FieldError, ValidationProblem


@dataclass(frozen=True, slots=True)
class Cursor:
    """The position after the last item of a page: its start and its id."""

    starts_at: datetime
    id: UUID


def encode(starts_at: datetime, event_id: UUID) -> str:
    """Return the cursor that continues after the item `(starts_at, event_id)`."""
    payload = {"startsAt": starts_at.astimezone(UTC).isoformat(), "id": str(event_id)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode(raw: str) -> Cursor:
    """Read a cursor back.

    Raises:
        ValidationProblem: `invalid_cursor` for anything that this module did not write.
    """
    try:
        data = json.loads(base64.urlsafe_b64decode(raw.encode()))
        starts_at = datetime.fromisoformat(data["startsAt"])
        if starts_at.tzinfo is None or not representable(starts_at):
            raise ValueError("naive or out of range")
        return Cursor(starts_at, UUID(data["id"]))
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValidationProblem(
            "Invalid cursor.",
            code="invalid_cursor",
            errors=[FieldError(field="cursor", msg="invalid")],
        ) from exc
