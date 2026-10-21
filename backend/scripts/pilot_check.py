"""Pilot check (M5 12.4): count the public events with a poster on a target instance.

Reads only the public feed (`GET /api/public/feed/events`), page by page, and prints how many
upcoming events carry an image, the number that the pilot criterion asks for (at least 10).

    uv run python -m scripts.pilot_check https://events.reutlingen.university
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import httpx

REQUIRED = 10
PAGE = 200


def upcoming_with_image(base_url: str, now: datetime) -> tuple[int, int]:
    """Return `(upcoming with image, all upcoming)` from the public feed of `base_url`."""
    with_image = total = 0
    cursor: str | None = None
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=20) as client:
        while True:
            params = {
                "limit": PAGE,
                "from": now.isoformat(),
                **({"cursor": cursor} if cursor else {}),
            }
            body = client.get("/api/public/feed/events", params=params).raise_for_status().json()
            for item in body["items"]:
                total += 1
                with_image += item["image"] is not None and item["status"] != "cancelled"
            cursor = body["nextCursor"]
            if cursor is None:
                return with_image, total


def main(argv: list[str]) -> int:
    """Print the count and return 1 when it is below the pilot criterion."""
    if len(argv) != 2:
        print("usage: python -m scripts.pilot_check <base-url>", file=sys.stderr)
        return 2
    with_image, total = upcoming_with_image(argv[1], datetime.now(UTC))
    verdict = "ok" if with_image >= REQUIRED else "below the pilot criterion"
    print(
        f"pilot_check: {with_image}/{total} upcoming events with image ({verdict}, need {REQUIRED})"
    )
    return 0 if with_image >= REQUIRED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
