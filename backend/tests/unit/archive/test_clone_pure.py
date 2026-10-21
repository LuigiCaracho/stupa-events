"""Clone dates, due offsets and the relation: the pure parts of `archive.clone`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.archive.access import ArchiveRead
from app.modules.archive.clone import clone_times, offset_of, relation_of, source_parts
from app.modules.archive.schemas import CloneIn
from app.shared.errors import ValidationProblem


def source(**over: object) -> SimpleNamespace:
    base = {
        "all_day": False,
        "tzid": "Europe/Berlin",
        "starts_at": datetime(2026, 7, 10, 18, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 7, 10, 21, 30, tzinfo=UTC),
        "starts_on": None,
        "ends_on": None,
        "end_estimated": False,
    }
    return SimpleNamespace(**{**base, **over})


def body(**over: object) -> CloneIn:
    return CloneIn(**{"startsAt": datetime(2026, 12, 1, 18, tzinfo=UTC), **over})  # type: ignore[arg-type]


def test_a_timed_template_keeps_its_duration() -> None:
    start, end, estimated, days = clone_times(source(), body())  # type: ignore[arg-type]
    assert (end - start).total_seconds() == 3.5 * 3600 and not estimated and days is None


def test_the_duration_survives_the_change_to_winter_time() -> None:
    summer = source(
        starts_at=datetime(2026, 10, 24, 20, 0, tzinfo=UTC),
        ends_at=datetime(2026, 10, 25, 3, 0, tzinfo=UTC),
    )
    start = datetime(2026, 10, 24, 20, tzinfo=UTC)
    _, end, *_ = clone_times(summer, body(startsAt=start))  # type: ignore[arg-type]
    assert (end - start).total_seconds() == 7 * 3600


def test_an_explicit_end_wins_and_a_wrong_one_is_refused() -> None:
    explicit = body(endsAt=datetime(2026, 12, 1, 19, tzinfo=UTC))
    assert clone_times(source(), explicit)[1] == datetime(2026, 12, 1, 19, tzinfo=UTC)  # type: ignore[arg-type]
    with pytest.raises(ValidationProblem):
        clone_times(source(), body(endsAt=datetime(2026, 12, 1, 17, tzinfo=UTC)))  # type: ignore[arg-type]


def test_an_estimated_end_stays_estimated_only_when_derived() -> None:
    estimated = source(end_estimated=True)
    assert clone_times(estimated, body())[2] is True  # type: ignore[arg-type]
    assert clone_times(estimated, body(endsAt=datetime(2026, 12, 1, 20, tzinfo=UTC)))[2] is False  # type: ignore[arg-type]


def test_an_all_day_template_keeps_its_days_across_the_change() -> None:
    template = source(all_day=True, starts_on=date(2026, 3, 27), ends_on=date(2026, 3, 29))
    start, end, _, days = clone_times(
        template, body(startsAt=datetime(2026, 10, 24, 22, 30, tzinfo=UTC))
    )  # type: ignore[arg-type]
    assert days == (date(2026, 10, 25), date(2026, 10, 27))
    assert start == datetime(2026, 10, 24, 22, tzinfo=UTC) and end == datetime(
        2026, 10, 27, 23, tzinfo=UTC
    )


def item(**over: object) -> SimpleNamespace:
    return SimpleNamespace(**{"due_offset_days": None, "due_at": None, **over})


@pytest.mark.parametrize(
    ("kwargs", "want"),
    [
        ({"due_offset_days": -7}, -7),
        ({}, None),
        ({"due_at": datetime(2026, 7, 1, 7, tzinfo=UTC)}, -9),
        ({"due_at": datetime(2026, 7, 25, 7, tzinfo=UTC)}, 15),
        ({"due_at": datetime(2020, 1, 1, tzinfo=UTC)}, -365),
        ({"due_at": datetime(2030, 1, 1, tzinfo=UTC)}, 365),
    ],
)
def test_due_offsets(kwargs: dict, want: int | None) -> None:
    assert offset_of(item(**kwargs), source()) == want  # type: ignore[arg-type]


def test_relation_names() -> None:
    event = SimpleNamespace(id=uuid4())
    assert relation_of(ArchiveRead(event, True)) == "own"  # type: ignore[arg-type]
    assert relation_of(ArchiveRead(event, False)) == "foreign"  # type: ignore[arg-type]
    assert source_parts
