"""Search input: parsing, modes, limits, transliteration and highlight segments."""

from __future__ import annotations

import pytest

from app.modules.search.segments import START, STOP, Segment, highlight, segments
from app.modules.search.translit import translit
from app.modules.search.words import Word, parse
from app.shared.errors import ValidationProblem


def test_plain_words_are_split_and_short_ones_stay_out_of_the_trigram() -> None:
    assert parse("Movie night") == [Word("Movie", "Movie", True), Word("night", "night", True)]
    assert [w.fuzzy for w in parse("LAN am Party")] == [True, False, True]
    assert parse("  Huettencafe ") == [Word("Huettencafe", "Huttencafe", True)]


def test_syntax_inputs_run_through_full_text_only_as_one_piece() -> None:
    for q in ('"movie night"', "kino -popcorn", "kino OR party", "-kino x", "kino or party"):
        words = parse(q)
        assert len(words) == 1 and words[0].fuzzy is False and words[0].text == q.strip()


def test_inputs_below_two_characters_have_no_words_and_long_ones_are_cut_to_eight_words() -> None:
    assert parse(None) == [] and parse("") == [] and parse("x") == [] and parse("   ") == []
    assert len(parse(" ".join(f"wort{i}" for i in range(12)))) == 8


@pytest.mark.parametrize(
    ("q", "code"), [("x" * 101, "query_too_long"), ("a\x00b", "invalid_query")]
)
def test_forbidden_inputs(q: str, code: str) -> None:
    with pytest.raises(ValidationProblem) as caught:
        parse(q)
    assert caught.value.code == code
    assert len(parse("x" * 100)) == 1


@pytest.mark.parametrize(
    ("typed", "folded"),
    [
        ("Huettencafe", "Huttencafe"),
        ("Praesidium", "Prasidium"),
        ("Loeten", "Loten"),
        ("QUELLE", "QULLE"),
        ("Haus", "Haus"),
        ("Übung", "Übung"),
        ("Aeolus", "Aolus"),
    ],
)
def test_translit(typed: str, folded: str) -> None:
    assert translit(typed) == folded


def test_segments_cut_at_the_marks_and_keep_html_as_text() -> None:
    marked = f"a {START}Film{STOP} <b>b</b> {START}Abend{STOP}"
    assert segments(marked) == [
        Segment(text="a ", hit=False),
        Segment(text="Film", hit=True),
        Segment(text=" <b>b</b> ", hit=False),
        Segment(text="Abend", hit=True),
    ]
    assert segments("nur Text") == [Segment(text="nur Text", hit=False)]
    assert segments(f"{START}ganz{STOP}") == [Segment(text="ganz", hit=True)]


def test_highlight_needs_a_hit() -> None:
    assert highlight("title", None) is None and highlight("title", "") is None
    assert highlight("title", "ohne Treffer") is None
    found = highlight("title", f"{START}Film{STOP}")
    assert found is not None and found.field == "title" and found.segments[0].hit
