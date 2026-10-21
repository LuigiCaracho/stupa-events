"""`missing_info`: what a dossier still lacks, as hints and never as locks.

A pure function over `HintInput`, which the loader in `hints_data.py` builds with a few
grouped queries. A hint is `{code, severity, field}`; the German text comes from the client
(`hints.<code>`). The only hard rule of the platform is `publish_incomplete` (`publish.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

type Severity = Literal["info", "warn"]


@dataclass(frozen=True, slots=True)
class PosterFacts:
    """The facts about the current poster that the hints read."""

    scan_status: str
    has_derivatives: bool
    alt_text: str | None
    credit: str | None
    persons_depicted: bool
    consent_note: str | None

    @property
    def consent_missing(self) -> bool:
        """Tell if depicted persons lack a consent note (the poster stays out of the feed)."""
        return self.persons_depicted and not (self.consent_note or "").strip()

    @property
    def ready(self) -> bool:
        """Tell if the file is scanned clean and derived."""
        return self.scan_status == "clean" and self.has_derivatives


@dataclass(frozen=True, slots=True)
class HintInput:
    """The facts of a dossier that the hints read."""

    state: str
    organization_id: UUID | None
    now: datetime
    ends_at: datetime
    summary: str | None
    primary_category_id: UUID | None
    venue_id: UUID | None
    venue_text: str | None
    location_confirmed: bool
    poster: PosterFacts | None
    facts_error: str | None
    howto_present: bool
    outcome_answered: bool


@dataclass(frozen=True, slots=True)
class Hint:
    """One hint: a stable code, how much it weighs and the field it points to."""

    code: str
    severity: Severity
    field: str | None


def _blank(value: str | None) -> bool:
    return not (value or "").strip()


def _poster_hints(item: HintInput) -> list[Hint]:
    poster = item.poster
    if poster is None:
        return [Hint("no_poster", "warn" if item.state == "published" else "info", "poster")]
    found = []
    if not poster.ready:
        found.append(Hint("poster_not_ready", "warn", "poster"))
    if poster.consent_missing:
        found.append(Hint("poster_consent_missing", "warn", "poster"))
    if _blank(poster.alt_text):
        found.append(Hint("poster_alt_missing", "info", "poster"))
    if _blank(poster.credit):
        found.append(Hint("poster_credit_missing", "info", "poster"))
    return found


def _content_hints(item: HintInput) -> list[Hint]:
    no_venue = item.venue_id is None and _blank(item.venue_text)
    unconfirmed = (
        item.venue_id is None and not _blank(item.venue_text) and not item.location_confirmed
    )
    checks = (
        (item.organization_id is None, Hint("no_organization", "warn", "organizationId")),
        (_blank(item.summary), Hint("no_summary", "info", "summary")),
        (item.primary_category_id is None, Hint("no_category", "info", "primaryCategoryId")),
        (no_venue, Hint("no_venue", "info", "venueId")),
        (unconfirmed, Hint("location_unconfirmed", "warn", "venueText")),
        (item.facts_error is not None, Hint("facts_incomplete", "info", item.facts_error)),
        (not item.howto_present, Hint("howto_missing", "info", "howto")),
        (
            item.now >= item.ends_at and not item.outcome_answered,
            Hint("outcome_open", "info", "outcome"),
        ),
    )
    return [hint for hit, hint in checks if hit]


def missing_info(item: HintInput) -> list[Hint]:
    """List the hints of a dossier: the poster first, then the content, then the follow-up."""
    return [*_poster_hints(item), *_content_hints(item)]


def warning_count(hints: list[Hint]) -> int:
    """Count the hints of severity `warn`."""
    return sum(1 for hint in hints if hint.severity == "warn")
