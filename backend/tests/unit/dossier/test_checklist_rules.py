"""Due dates of checklist items and the seed templates (contract 2.4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.dossier.checklist_due import due_at_for
from app.modules.dossier.checklist_seed import read_seed

BERLIN = "Europe/Berlin"


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_minus_28_days_is_09_00_local_time() -> None:
    assert due_at_for(utc(2026, 11, 14, 18, 0), BERLIN, -28) == utc(2026, 10, 17, 7, 0)


def test_the_end_of_summer_time_moves_the_utc_hour() -> None:
    assert due_at_for(utc(2026, 11, 2, 18, 0), BERLIN, -8) == utc(2026, 10, 25, 8, 0)
    assert due_at_for(utc(2026, 10, 30, 18, 0), BERLIN, -7) == utc(2026, 10, 23, 7, 0)


def test_the_start_of_summer_time_in_2027() -> None:
    assert due_at_for(utc(2027, 3, 30, 18, 0), BERLIN, -3) == utc(2027, 3, 27, 8, 0)
    assert due_at_for(utc(2027, 3, 30, 18, 0), BERLIN, 0) == utc(2027, 3, 30, 7, 0)


def test_the_local_date_decides_not_the_utc_date() -> None:
    assert due_at_for(utc(2026, 7, 4, 22, 30), BERLIN, 0) == utc(2026, 7, 5, 7, 0)


@pytest.mark.parametrize(("starts", "offset"), [(None, -7), (utc(2026, 7, 4, 10), None)])
def test_without_start_or_offset_there_is_no_due_date(
    starts: datetime | None, offset: int | None
) -> None:
    assert due_at_for(starts, BERLIN, offset) is None


def test_seed_templates_are_complete_and_stable() -> None:
    templates, items = read_seed()
    assert {t["slug"] for t in templates} == {"generic", "party", "meeting", "trip"}
    by_template: dict[object, list[dict]] = {}
    for item in items:
        by_template.setdefault(item["template_id"], []).append(item)
    sizes = {t["slug"]: len(by_template[t["id"]]) for t in templates}
    assert sizes == {"generic": 6, "party": 9, "meeting": 2, "trip": 4}
    assert len({i["id"] for i in items}) == len(items)
    assert read_seed() == (templates, items)
    offsets = {i["key"]: i["due_offset_days"] for i in items}
    assert offsets["order-poster"] == -28 and offsets["confirm-tech"] == -7
    assert offsets["settlement"] == 7
