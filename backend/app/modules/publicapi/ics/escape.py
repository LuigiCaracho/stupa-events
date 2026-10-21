"""Text values of iCalendar (RFC 5545 section 3.3.11): clean first, then escape.

Control characters (CR, LF, NEL, U+2028/2029 included) never reach the file: they become a
space before the backslash, semicolon and comma are escaped. A multi-line value (the
`DESCRIPTION`) is given as a list of lines and joined with the two characters `\\n`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


def clean(value: str) -> str:
    """Replace every control character by a space."""
    return _CONTROL.sub(" ", value)


def escape(value: str) -> str:
    """Escape backslash, semicolon and comma of an already cleaned text."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def text(value: str) -> str:
    """Return a single-line TEXT value: cleaned and escaped."""
    return escape(clean(value))


def lines(values: Iterable[str]) -> str:
    """Return a multi-line TEXT value: each line cleaned and escaped, joined by `\\n`."""
    return "\\n".join(text(line) for line in values)
