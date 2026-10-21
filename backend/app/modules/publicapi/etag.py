"""`If-None-Match` for the public routes: weak validators and `*` count as a match."""

from __future__ import annotations


def matches(header: str | None, etag: str) -> bool:
    """Tell if an `If-None-Match` header names `etag` (or `*`)."""
    if header is None:
        return False
    candidates = {part.strip().removeprefix("W/") for part in header.split(",")}
    return "*" in candidates or etag in candidates
