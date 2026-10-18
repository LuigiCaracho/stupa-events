"""Wire shapes of the pipeline: reasons and the guard report (camelCase)."""

from __future__ import annotations

from app.modules.auth.schemas import CamelModel
from app.modules.pipeline.reasons import Reason


class ReasonOut(CamelModel):
    """A blocker or warning of a guard."""

    code: str
    field: str | None
    severity: str
    message_key: str
    fix_action: str | None


class GuardsOut(CamelModel):
    """Guard list of a transition, computed on request and never stored."""

    transition: str
    allowed: bool
    reasons: list[ReasonOut]


def reason_out(reason: Reason) -> ReasonOut:
    """Map a reason to its wire shape."""
    return ReasonOut(
        code=reason.code,
        field=reason.field,
        severity=reason.severity.value,
        message_key=reason.message_key,
        fix_action=reason.fix_action.value if reason.fix_action else None,
    )
