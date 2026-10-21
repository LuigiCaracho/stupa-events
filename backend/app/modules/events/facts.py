"""The facts profile of a dossier: a union by `category.required_profile` (PLAN 3.4).

`event.facts` holds the camelCase keys of exactly one profile (`generic`, `party`, `meeting`,
`trip`), all models `extra=forbid`. `parse` validates a body against the profile, `error_for`
names the first field that blocks `factsValid` (T02), and `fit` keeps the keys that the
profile of a new category knows and reports the rest. Only "party without `ageLimit`" and
"minimum above maximum" block; everything else is optional.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, Field, ValidationError

from app.modules.auth.schemas import CamelModel

Profile = Literal["generic", "party", "meeting", "trip"]
Count = Annotated[int, Field(ge=0, le=1_000_000)] | None
Line = Annotated[str, Field(max_length=200)] | None


class GenericFacts(CamelModel):
    """Capacity and budget of any dossier."""

    capacity: Count = None
    budget_cents: Count = None


class PartyFacts(CamelModel):
    """A party needs the age limit; the security plan and the noise permit are tracked."""

    age_limit: Literal[0, 16, 18] | None = None
    capacity: Count = None
    security_plan_done: bool | None = None
    noise_permit_ref: Line = None
    budget_cents: Count = None


class MeetingFacts(CamelModel):
    """A meeting: agenda, quorum and who writes the minutes."""

    agenda_md: Annotated[str, Field(max_length=20000)] | None = None
    quorum_needed: Count = None
    protocol_owner: Line = None


class TripFacts(CamelModel):
    """A trip: meeting point, price, participants and the sign-up."""

    meeting_point: Line = None
    price_text: Line = None
    min_participants: Count = None
    max_participants: Count = None
    signup_url: (
        Annotated[str, Field(max_length=500, pattern=r"^https://[^/@\s]+\.[^/@\s]+")] | None
    ) = None
    signup_deadline: AwareDatetime | None = None


MODELS: dict[str, type[CamelModel]] = {
    "generic": GenericFacts,
    "party": PartyFacts,
    "meeting": MeetingFacts,
    "trip": TripFacts,
}
RESET_ON_CLONE = frozenset({"securityPlanDone", "noisePermitRef", "signupUrl", "signupDeadline"})


def parse(profile: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate `raw` against the profile and return the stored form (camelCase, no nulls).

    Raises:
        pydantic.ValidationError: A key is unknown to the profile or a value is invalid.
    """
    model = MODELS[profile].model_validate(raw)
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


def error_for(profile: str, facts: dict[str, Any] | None) -> str | None:
    """Return the API name of the first field that blocks `factsValid`, else `None`."""
    facts = facts or {}
    if profile == "party" and facts.get("ageLimit") is None:
        return "facts.ageLimit"
    low, high = facts.get("minParticipants"), facts.get("maxParticipants")
    if profile == "trip" and low is not None and high is not None and low > high:
        return "facts.minParticipants"
    return None


def fit(profile: str, facts: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Keep the keys that `profile` knows; return the kept facts and the dropped keys."""
    known = {field.alias or name for name, field in MODELS[profile].model_fields.items()}
    kept = {k: v for k, v in (facts or {}).items() if k in known}
    return kept, sorted(set(facts or {}) - known)


def validation_errors(exc: ValidationError) -> list[tuple[str, str]]:
    """Reduce a validation error to `(field, message)` pairs for the 422 body."""
    return [(".".join(str(p) for p in e["loc"]), e["msg"]) for e in exc.errors()]
