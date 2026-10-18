"""The columns a transition writes, as a pure function of the transition table."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.pipeline.transitions import Transition


def transition_values(
    transition: Transition,
    *,
    actor_sub: str,
    rev: int,
    public_seq: int,
    publish_at: datetime | None,
    slug: str | None,
) -> dict[str, Any]:
    """Return the `UPDATE` values of a transition besides `rev`.

    Args:
        transition: The transition being fired.
        actor_sub: The firing sub (for the `actor` rule).
        rev: The revision being replaced; `new_rev` writes `rev + 1`.
        public_seq: The current `public_seq`; `plus_one` writes `public_seq + 1`.
        publish_at: The `publishAt` of the request (rule `body`).
        slug: The final slug when the transition assigns one.
    """
    values: dict[str, Any] = {"state": transition.target.value}
    for column, rule in transition.sets:
        match rule:
            case "actor":
                values[column] = actor_sub
            case "null":
                values[column] = None
            case "plus_one":
                values[column] = public_seq + 1
            case "new_rev":
                values[column] = rev + 1
            case "body":
                values[column] = publish_at
            case "slug":
                values[column] = slug
            case "scheduled":
                values.update(
                    public_status="scheduled", public_reason_code="none", public_reason_text=None
                )
            case unknown:
                raise ValueError(f"unknown rule {unknown!r} for {column}")
    return values
