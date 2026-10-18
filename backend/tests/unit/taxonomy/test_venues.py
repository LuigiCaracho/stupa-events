"""Venue helpers: slugs, the room key and the building number (all pure)."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.modules.taxonomy.venues import building_of, normalize_room_key, slugify

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("9-U09", "9-u9"),
        ("Raum 9-U09", "9-u9"),
        ("9-u009", "9-u9"),
        ("9-229", "9-229"),
        ("5-015", "5-015"),
        ("17-U14", "17-u14"),
        ("  Raum   17 - U14 ", "17-u14"),
        ("Senatssaal", None),
        ("", None),
        (None, None),
    ],
)
def test_room_key_examples(text: str | None, key: str | None) -> None:
    assert normalize_room_key(text) == key


@given(st.text(max_size=30))
def test_room_key_is_idempotent_and_lower_case(text: str) -> None:
    key = normalize_room_key(text)
    if key is not None:
        assert key == key.lower() and " " not in key
        assert normalize_room_key(key) == key


@given(st.integers(1, 99), st.sampled_from(["", "u", "U"]), st.integers(1, 999))
def test_room_key_of_a_generated_room(building: int, prefix: str, number: int) -> None:
    key = normalize_room_key(f"{building}-{prefix}{number:03d}")
    assert key is not None and key.startswith(f"{building}-{prefix.lower()}")
    assert key.endswith(str(number)) if prefix else key == f"{building}-{number:03d}"


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Göckelesmaier Festzelt", "goeckelesmaier-festzelt"),
        ("Kart & Fun Neckartenzlingen", "kart-fun-neckartenzlingen"),
        ("FSC Calw e.V.", "fsc-calw-e-v"),
        ("Straßburg", "strassburg"),
        ("  --Hades--  ", "hades"),
    ],
)
def test_slugify_examples(name: str, slug: str) -> None:
    assert slugify(name) == slug


@given(st.text(min_size=1, max_size=120))
def test_slugify_yields_a_valid_slug_or_nothing(name: str) -> None:
    slug = slugify(name)
    assert slug == "" or SLUG.fullmatch(slug)


@pytest.mark.parametrize(
    ("name", "building"),
    [
        ("Kinosaal 9-133", "9"),
        ("Raum 17-U14", "17"),
        ("Aula Building 6", "6"),
        ("Geb. 17 Pavillon", "17"),
        ("Präsidium Gebäude 3", "3"),
        ("Rasen zwischen Geb. 3 und Geb. 1", None),
        ("Hades", None),
    ],
)
def test_building_of(name: str, building: str | None) -> None:
    assert building_of(name) == building
