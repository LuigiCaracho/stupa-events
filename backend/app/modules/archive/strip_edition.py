"""Strip the semester and year marks from a title, so a new edition does not inherit them."""

from __future__ import annotations

import re

_EDITION = re.compile(
    r"""
      \b(?:WS|WiSe|SoSe|SS)\s*\d{2,4}(?:\s*/\s*\d{2,4})?\b
    | \b(?:Winter|Sommer)semester\s*\d{4}(?:\s*/\s*\d{2,4})?\b
    | \b(?:19|20)\d{2}(?:\s*/\s*(?:19|20)?\d{2})?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)
_EMPTY_BRACKETS = re.compile(r"[(\[]\s*[)\]]")
_EDGE = re.compile(r"^[\s\-–—:|,/]+|[\s\-–—:|,/]+$")
_SPACES = re.compile(r"\s{2,}")


def strip_edition(title: str) -> str:
    """Remove semester ("WS26/27", "SoSe 2026") and year ("2026", "2026/27") marks.

    A title that consists of nothing else keeps its text.
    """
    cleaned = _EDITION.sub("", title)
    cleaned = _EMPTY_BRACKETS.sub("", cleaned)
    cleaned = _SPACES.sub(" ", _EDGE.sub("", cleaned)).strip()
    return cleaned or title
