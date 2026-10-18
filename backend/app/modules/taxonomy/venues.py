"""Pure helpers for venue rows: slugs and the normalised room key.

`normalize_room_key` follows PLAN 3.3: lower case, no `Raum` prefix, no blanks, and the
zeros directly after a letter prefix of the room number are dropped (`9-U09` becomes
`9-u9`). Digits-only room numbers keep their zeros (`5-015`).
"""

from __future__ import annotations

import re
from typing import Final

_UMLAUTS: Final = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_ROOM: Final = re.compile(r"^(?P<building>\d{1,3})-(?P<prefix>[a-z]*)(?P<number>\d{1,4})$")
_BUILDING: Final = re.compile(r"\b(?:geb\.?|gebäude|building)\s*(\d{1,3})\b", re.IGNORECASE)


def slugify(name: str) -> str:
    """Turn a venue name into a slug (`^[a-z0-9][a-z0-9-]{0,59}$`), umlauts transliterated."""
    folded = name.lower().translate(_UMLAUTS)
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:60].strip("-")


def normalize_room_key(text: str | None) -> str | None:
    """Return the normalised room key of `text`, or `None` when it names no room.

    Args:
        text: A free text such as `Raum 9-U09` or `9-229`.
    """
    if not text:
        return None
    compact = re.sub(r"^\s*raum\s+", "", text.strip().lower())
    match = _ROOM.fullmatch(re.sub(r"\s+", "", compact))
    if match is None:
        return None
    prefix, number = match["prefix"], match["number"]
    if prefix:
        number = number.lstrip("0") or "0"
    return f"{match['building']}-{prefix}{number}"


def building_of(name: str) -> str | None:
    """Return the building number a venue name states, or `None` when it is unclear."""
    room = re.search(r"\b(\d{1,3})-[uU]?\d{1,4}\b", name)
    if room:
        return room[1]
    found = {m[1] for m in _BUILDING.finditer(name)}
    return found.pop() if len(found) == 1 else None
