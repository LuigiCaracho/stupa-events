"""The only hard rule of `publish`: a title, a start and an organization.

Everything else the platform knows about a dossier appears as a hint (`hints.py`), never as
a lock. `publish_incomplete` lists the missing fields with their API names.
"""

from __future__ import annotations

from app.modules.events.models import Event
from app.shared.errors import FieldError, ValidationProblem

REQUIRED: tuple[tuple[str, str], ...] = (
    ("title", "title"),
    ("starts_at", "startsAt"),
    ("organization_id", "organizationId"),
)


def missing_fields(event: Event) -> list[str]:
    """Return the API names of the required fields that are empty."""
    return [
        api
        for column, api in REQUIRED
        if (value := getattr(event, column)) is None
        or (isinstance(value, str) and not value.strip())
    ]


def require_complete(event: Event) -> None:
    """Raise 422 `publish_incomplete` when a required field is empty."""
    missing = missing_fields(event)
    if missing:
        raise ValidationProblem(
            "The dossier lacks the data to be published.",
            code="publish_incomplete",
            errors=[FieldError(field=name, msg="required") for name in missing],
            extensions={"reasons": [{"field": name} for name in missing]},
        )
