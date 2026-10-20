"""Line diff, attachment meta and mail template placeholders."""

from __future__ import annotations

import pytest

from app.modules.dossier.diff import MAX_DIFF_LINES, diff_lines
from app.modules.dossier.mail_templates import used_placeholders
from app.modules.files.attachment_meta import parse_meta
from app.shared.errors import ValidationProblem


def ops(old: str, new: str) -> list[tuple[str, str]]:
    return [(line.op, line.text) for line in diff_lines(old, new)]


def test_equal_texts_are_all_equal_with_line_numbers() -> None:
    lines = diff_lines("a\nb", "a\nb")
    assert [(line.op, line.from_line, line.to_line) for line in lines] == [
        ("equal", 1, 1),
        ("equal", 2, 2),
    ]


def test_insert_delete_and_replace() -> None:
    assert ops("a\nc", "a\nb\nc") == [("equal", "a"), ("add", "b"), ("equal", "c")]
    assert ops("a\nb\nc", "a\nc") == [("equal", "a"), ("remove", "b"), ("equal", "c")]
    assert ops("a\nb", "a\nx") == [("equal", "a"), ("remove", "b"), ("add", "x")]


def test_umlauts_and_crlf_compare_by_line() -> None:
    assert ops("Grüße\r\nÜber", "Grüße\nÜber €") == [
        ("equal", "Grüße"),
        ("remove", "Über"),
        ("add", "Über €"),
    ]


def test_the_numbers_of_removed_and_added_lines_follow_the_side() -> None:
    lines = diff_lines("a\nb", "a\nx\ny")
    assert [(line.op, line.from_line, line.to_line) for line in lines[1:]] == [
        ("remove", 2, None),
        ("add", None, 2),
        ("add", None, 3),
    ]


def test_a_diff_above_the_line_cap_is_422() -> None:
    big = "\n".join(["x"] * (MAX_DIFF_LINES + 1))
    with pytest.raises(ValidationProblem) as caught:
        diff_lines(big, "")
    assert caught.value.code == "diff_too_large"


def test_meta_models_are_closed_per_kind() -> None:
    assert parse_meta("poster", {"format": "a3", "width": 10}) == {"format": "a3", "width": 10}
    assert parse_meta("quote", {}) == {}
    with pytest.raises(ValidationProblem):
        parse_meta("quote", {"amountCents": 5})
    with pytest.raises(ValidationProblem):
        parse_meta("poster", {"format": "a9"})
    assert parse_meta("other", {"note": "x"}) == {"note": "x"}
    assert (
        parse_meta("social_post", {"channel": "instagram", "status": "draft"})["channel"]
        == "instagram"
    )


def test_used_placeholders_are_sorted_and_unique() -> None:
    text = "{{ event.title }} um {{event.starts_local}} bei {{ venue.name }} {{ event.title }}"
    assert used_placeholders("Betreff {{ org.name }}", text) == [
        "event.starts_local",
        "event.title",
        "org.name",
        "venue.name",
    ]
