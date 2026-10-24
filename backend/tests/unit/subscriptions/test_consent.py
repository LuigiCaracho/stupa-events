"""Consent texts: rendering and the golden file that pins every version forever."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.subscriptions import consent

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "consent.json"


def test_every_version_matches_the_golden_file_byte_for_byte() -> None:
    pinned = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for version, template in pinned.items():
        assert consent.TEMPLATES[version] == template
    assert consent.CURRENT_VERSION in pinned


def test_labels_are_joined_for_a_german_sentence() -> None:
    assert consent.join_labels([]) == ""
    assert consent.join_labels(["A"]) == "A"
    assert consent.join_labels(["A", "B"]) == "A und B"
    assert consent.join_labels(["A", "B", "C"]) == "A, B und C"


def test_the_sentence_names_the_chosen_interests() -> None:
    sentence = consent.render(consent.CURRENT_VERSION, ["Partys und Feiern", "Gaming und LAN"])
    assert sentence == (
        "Ich möchte wöchentlich eine Mail zu Partys und Feiern und Gaming und LAN. "
        "Abmelden geht jederzeit mit einem Klick."
    )
