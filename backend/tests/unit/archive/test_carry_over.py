"""The carry-over table: one rule per part, the report from it, the facts reset."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.archive import carry_over
from app.modules.archive.carry_over import CARRY_OVER, RULES, SourceCounts, plan, reset_facts
from app.modules.archive.clonable import clonable_clause, is_clonable


def test_each_part_has_exactly_one_rule() -> None:
    parts = [rule.part for rule in CARRY_OVER]
    assert len(parts) == len(set(parts)) == len(RULES)
    assert all(rule.reason.startswith("clone.reason.") for rule in CARRY_OVER)


@pytest.mark.parametrize(
    ("part", "own", "foreign"),
    [
        ("title", "copy", "copy"),
        ("venueText", "reset", "reset"),
        ("documents", "copy", "partial"),
        ("checklist", "copy", "partial"),
        ("poster", "never", "never"),
        ("files", "never", "never"),
        ("socialPosts", "never", "never"),
        ("links", "never", "never"),
        ("history", "never", "never"),
        ("shared", "link", "link"),
    ],
)
def test_the_table_of_the_contract(part: str, own: str, foreign: str) -> None:
    assert (RULES[part].mode("own"), RULES[part].mode("foreign")) == (own, foreign)


def test_the_report_has_a_line_per_rule_with_counts_and_the_howto_link() -> None:
    report = plan("own", SourceCounts(documents=3, howto_linked=True, checklist=7))
    assert [line.part for line in report] == [rule.part for rule in CARRY_OVER]
    by_part = {line.part: line for line in report}
    assert by_part["documents"].count == 3 and by_part["checklist"].count == 7
    assert by_part["howto"].mode == "link" and by_part["title"].count is None
    copied = plan("foreign", SourceCounts(documents=0, howto_linked=False, checklist=0))
    assert {line.part: line.mode for line in copied}["howto"] == "copy"
    assert plan("foreign", SourceCounts(0, False, 0)) == copied


def test_facts_reset_drops_expiring_keys_and_keeps_few_for_foreign_templates() -> None:
    facts = {
        "ageLimit": 18,
        "capacity": 100,
        "minParticipants": 4,
        "maxParticipants": 40,
        "securityPlanDone": True,
        "noisePermitRef": "X",
        "budgetCents": 500,
        "priceText": "20 Euro",
        "meetingPoint": "Hbf",
        "protocolOwner": "Ada",
        "agendaMd": "# Tops",
    }
    assert reset_facts(facts, "own") == {
        "ageLimit": 18,
        "capacity": 100,
        "minParticipants": 4,
        "maxParticipants": 40,
        "budgetCents": 500,
        "priceText": "20 Euro",
        "meetingPoint": "Hbf",
        "protocolOwner": "Ada",
        "agendaMd": "# Tops",
    }
    assert reset_facts(facts, "foreign") == {
        "ageLimit": 18,
        "capacity": 100,
        "minParticipants": 4,
        "maxParticipants": 40,
    }
    assert reset_facts(None, "own") == {} and reset_facts(None, "foreign") == {}
    assert {"capacity", "ageLimit", "minParticipants", "maxParticipants"} == (
        carry_over.FACTS_KEPT_FOREIGN
    )


def test_the_facts_line_names_what_stays_for_a_foreign_template() -> None:
    counts = SourceCounts(0, False, 0)
    own = {line.part: line for line in plan("own", counts)}["facts"]
    foreign = {line.part: line for line in plan("foreign", counts)}["facts"]
    assert own.reason == "clone.reason.facts" and foreign.reason == "clone.reason.factsForeign"


@pytest.mark.parametrize(
    ("state", "own", "want"),
    [
        ("archived", True, True),
        ("archived", False, True),
        ("published", True, True),
        ("published", False, False),
        ("draft", True, False),
        ("draft", False, False),
    ],
)
def test_which_dossiers_are_templates(state: str, own: bool, want: bool) -> None:
    assert is_clonable(state, own) is want


def test_the_clonable_clause_for_a_scope_and_for_everybody() -> None:
    literal = {"literal_binds": True}
    scoped = clonable_clause({uuid4()}).compile(compile_kwargs=literal)
    assert "event.state = 'archived'" in str(scoped) and "organization_id IN" in str(scoped)
    everybody = clonable_clause(None).compile(compile_kwargs=literal)
    assert "organization_id IN" not in str(everybody)
