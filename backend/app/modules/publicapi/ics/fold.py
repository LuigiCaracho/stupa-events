"""Line folding of iCalendar (RFC 5545 section 3.1): 75 octets, never inside a character."""

from __future__ import annotations

LIMIT = 75
CRLF = "\r\n"


def fold(line: str) -> str:
    """Fold `line` into physical lines of at most 75 octets without the line break.

    A continuation line starts with one space, which counts. A UTF-8 character is never
    split, so a ZWJ emoji sequence is cut between its code points, which the RFC allows.
    """
    parts: list[str] = []
    current, size = "", 0
    for char in line:
        width = len(char.encode())
        if size + width > LIMIT:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return CRLF.join(parts)
