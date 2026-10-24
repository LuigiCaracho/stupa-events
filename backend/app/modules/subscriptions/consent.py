"""Versioned consent texts of the mail subscription (B3-KONTRAKT 5.5).

The person confirms the sentence they saw: the client sends the version, the server accepts
only the current one. A wording change is a new version; old versions stay here for good and
`tests/golden/consent.json` pins every one byte for byte. `{categories}` is the list of the
interest labels the person chose.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

CURRENT_VERSION: Final = "2026-10-1"
TEMPLATES: Final[dict[str, str]] = {
    "2026-10-1": (
        "Ich möchte wöchentlich eine Mail zu {categories}. Abmelden geht jederzeit mit einem Klick."
    ),
}
PRIVACY_URL: Final = "/datenschutz"


def join_labels(labels: Sequence[str]) -> str:
    """Join labels for a German sentence: `A`, `A und B`, `A, B und C`."""
    if len(labels) <= 1:
        return "".join(labels)
    return f"{', '.join(labels[:-1])} und {labels[-1]}"


def render(version: str, labels: Sequence[str]) -> str:
    """Return the sentence of `version` for the chosen interest labels.

    Raises:
        KeyError: `version` is not a known consent version.
    """
    return TEMPLATES[version].replace("{categories}", join_labels(labels))
