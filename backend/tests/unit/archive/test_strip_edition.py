"""`strip_edition` removes semester and year marks and nothing else."""

from __future__ import annotations

import pytest

from app.modules.archive.strip_edition import strip_edition


@pytest.mark.parametrize(
    ("title", "stripped"),
    [
        ("Movienight WS26/27", "Movienight"),
        ("Movienight WS 26/27", "Movienight"),
        ("Campusfest 2026", "Campusfest"),
        ("FSI LAN-Party 2026/27", "FSI LAN-Party"),
        ("Skiausfahrt SoSe26 Davos", "Skiausfahrt Davos"),
        ("Sommersemester 2026 Auftakt", "Auftakt"),
        ("Movienight (WS26/27)", "Movienight"),
        ("Movienight: Whiplash", "Movienight: Whiplash"),
        ("Movienight - 2026", "Movienight"),
        ("Party 2026 2027", "Party"),
        ("2026", "2026"),
        ("WS26/27", "WS26/27"),
        ("Haus 12345 Treff", "Haus 12345 Treff"),
    ],
)
def test_strip_edition(title: str, stripped: str) -> None:
    assert strip_edition(title) == stripped
