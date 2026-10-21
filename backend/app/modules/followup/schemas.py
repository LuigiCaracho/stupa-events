"""Wire shapes of the follow-up: the outcome of an event (contract 3.5).

Amounts are cents, the currency is always EUR. `waived = true` replaces the numbers by a
reason of at least ten characters. The outcome never reaches the feed, a card or the audit.
"""

from __future__ import annotations

import re
from typing import Annotated, Self

from pydantic import AfterValidator, Field, model_validator

from app.modules.auth.schemas import CamelModel
from app.shared.errors import FieldError, ValidationProblem

WAIVER_MIN_CHARS = 10
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f\u2028\u2029]")


def _notes(value: str | None) -> str | None:
    if value is None:
        return None
    if _CONTROL.search(value):
        raise ValueError("control characters are not allowed")
    return value.strip() or None


def _reason(value: str | None) -> str | None:
    if value is None:
        return None
    if _CONTROL.search(value) or "\n" in value:
        raise ValueError("control characters are not allowed")
    return value.strip() or None


Count = Annotated[int, Field(ge=0, le=100_000_000)]
Notes = Annotated[str | None, Field(max_length=2000), AfterValidator(_notes)]
Reason = Annotated[str | None, Field(max_length=300), AfterValidator(_reason)]


class OutcomeIn(CamelModel):
    """Body of `PUT /events/{id}/outcome`: it replaces the stored outcome entirely."""

    attendance: Count | None = None
    costs_cents: Count | None = None
    revenue_cents: Count | None = None
    notes: Notes = None
    waived: bool = False
    waived_reason: Reason = None

    @model_validator(mode="after")
    def _waiver_clears_numbers(self) -> Self:
        if self.waived:
            self.attendance = self.costs_cents = self.revenue_cents = None
        return self

    def stored(self) -> dict[str, object]:
        """Return the JSON stored in `event.outcome`.

        Raises:
            ValidationProblem: `waiver_reason_required` for a waiver without a real reason.
        """
        if self.waived and len(self.waived_reason or "") < WAIVER_MIN_CHARS:
            raise ValidationProblem(
                "Verzicht braucht einen Grund.",
                code="waiver_reason_required",
                errors=[FieldError(field="waivedReason", msg="at least 10 characters")],
            )
        return self.model_dump(by_alias=True)


class OutcomeOut(CamelModel):
    """The stored outcome of an event."""

    attendance: int | None = None
    costs_cents: int | None = None
    revenue_cents: int | None = None
    notes: str | None = None
    waived: bool = False
    waived_reason: str | None = None
