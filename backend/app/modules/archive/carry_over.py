"""The carry-over table of a clone (E11, PLAN 7.4): what a new edition inherits, as code.

`CARRY_OVER` holds one rule per part with the mode for an own and for a foreign template
dossier. `plan` turns the rules and the counts of the source into the report that the
preview shows, the clone returns and the interface lists (`clone.reason.*` are i18n keys).
The clone reads the same rules, so the table exists once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modules.auth.schemas import CamelModel

type Mode = Literal["copy", "reset", "partial", "link", "never"]
type Relation = Literal["own", "foreign"]


@dataclass(frozen=True, slots=True)
class Rule:
    """How one part of a dossier travels into the clone."""

    part: str
    own: Mode
    foreign: Mode
    reason: str

    def mode(self, relation: Relation) -> Mode:
        """Return the mode for the relation of the reader to the template."""
        return self.own if relation == "own" else self.foreign


CARRY_OVER: tuple[Rule, ...] = (
    Rule("title", "copy", "copy", "clone.reason.title"),
    Rule("summary", "copy", "copy", "clone.reason.text"),
    Rule("description", "copy", "copy", "clone.reason.text"),
    Rule("costText", "copy", "copy", "clone.reason.text"),
    Rule("category", "copy", "copy", "clone.reason.reference"),
    Rule("format", "copy", "copy", "clone.reason.reference"),
    Rule("venue", "copy", "copy", "clone.reason.reference"),
    Rule("venueText", "reset", "reset", "clone.reason.location"),
    Rule("facts", "partial", "partial", "clone.reason.facts"),
    Rule("documents", "copy", "partial", "clone.reason.documents"),
    Rule("howto", "copy", "copy", "clone.reason.howto"),
    Rule("checklist", "copy", "partial", "clone.reason.checklist"),
    Rule("poster", "never", "never", "clone.reason.poster"),
    Rule("imageException", "never", "never", "clone.reason.exception"),
    Rule("files", "never", "never", "clone.reason.files"),
    Rule("socialPosts", "never", "never", "clone.reason.social"),
    Rule("links", "never", "never", "clone.reason.links"),
    Rule("history", "never", "never", "clone.reason.history"),
    Rule("shared", "link", "link", "clone.reason.shared"),
)
RULES = {rule.part: rule for rule in CARRY_OVER}
FACT_RESET_FOREIGN = frozenset({"budgetCents", "priceText", "meetingPoint", "protocolOwner"})


class CarryOverLine(CamelModel):
    """One line of the clone report: a part, how it travels, why, and how many items."""

    part: str
    mode: Mode
    reason: str
    count: int | None = None


@dataclass(frozen=True, slots=True)
class SourceCounts:
    """What the source holds that a clone could take: documents, howto, checklist items."""

    documents: int
    howto_linked: bool
    checklist: int


def plan(relation: Relation, counts: SourceCounts) -> list[CarryOverLine]:
    """Build the report for a template: one line per rule, with counts where they matter."""
    sizes = {"documents": counts.documents, "checklist": counts.checklist}
    lines = []
    for rule in CARRY_OVER:
        mode = rule.mode(relation)
        if rule.part == "howto" and counts.howto_linked:
            mode = "link"
        lines.append(
            CarryOverLine(part=rule.part, mode=mode, reason=rule.reason, count=sizes.get(rule.part))
        )
    return lines


def reset_facts(facts: dict[str, object] | None, relation: Relation) -> dict[str, object]:
    """Return the clone facts without expiring keys (foreign: also costs and people)."""
    from app.modules.events.facts import RESET_ON_CLONE

    dropped = RESET_ON_CLONE | (FACT_RESET_FOREIGN if relation == "foreign" else frozenset())
    return {k: v for k, v in (facts or {}).items() if k not in dropped}
