"""Public one-line descriptions of the reference categories (shown on the category page and P07).

Kept apart from `reference.py` because migration `0002` inserts those rows before the column
`category.description` exists. Migration `0008` and `ensure_reference` fill only empty cells.
"""

from __future__ import annotations

from typing import Final

DESCRIPTIONS: Final[dict[str, str]] = {
    "kino": "Movienight und Filmabende",
    "party": "Partys und Tanzabende",
    "sitzung": "Sitzungen von Fachschaften und Gremien",
    "get-together": "Kneipentouren, Karaoke, Stammtische",
    "campusfest": "Das große Fest auf dem Campus",
    "festival": "Festivals rund um die Hochschule",
    "konzert": "Live-Musik",
    "workshop": "Ausprobieren und Mitmachen",
    "lan-party": "Game Together und LAN",
    "ausfahrt": "Ausflüge und Fahrten",
    "skiausfahrt": "Gemeinsam in den Schnee",
    "skydiving": "Fallschirmsprung für Mutige",
    "kart-fahren": "Gemeinsam auf der Kartbahn",
    "repair-cafe": "Löten, Reparieren, Ausprobieren",
    "cooking-class": "Gemeinsam kochen und essen",
}
