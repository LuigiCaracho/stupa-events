"""Parse a search input into words (contract 6.1, 6.2).

Two modes. Plain words are matched one by one, all of them must apply, each by full text or
by trigram similarity (typos, compounds). An input with quotes, a leading `-` or the word
`or` uses the web search syntax and is matched by full text only. Words shorter than three
characters never use the trigram. The input length is checked here, the rest is bound.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.search.translit import translit
from app.shared.errors import FieldError, ValidationProblem

MIN_QUERY, MAX_QUERY, MAX_WORDS, MIN_FUZZY = 2, 100, 8, 3
_SYNTAX = re.compile(r'"|(?:^|\s)-\S|(?:^|\s)or(?:\s|$)', re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Word:
    """One part of the input: the typed text, its transliteration and whether it may be fuzzy."""

    text: str
    folded: str
    fuzzy: bool


def parse(raw: str | None) -> list[Word]:
    """Split the input into words; an input below two characters yields no words.

    Raises:
        ValidationProblem: `query_too_long` above 100 characters, `invalid_query` for a NUL.
    """
    text = (raw or "").strip()
    if len(text) > MAX_QUERY:
        raise ValidationProblem(
            "Suchbegriff zu lang (höchstens 100 Zeichen).",
            code="query_too_long",
            errors=[FieldError(field="q", msg="too long")],
        )
    if "\x00" in text:
        raise ValidationProblem(
            "Ungültiger Suchbegriff.",
            code="invalid_query",
            errors=[FieldError(field="q", msg="invalid")],
        )
    if len(text) < MIN_QUERY:
        return []
    if _SYNTAX.search(text):
        return [Word(text, translit(text), fuzzy=False)]
    return [Word(w, translit(w), fuzzy=len(w) >= MIN_FUZZY) for w in text.split()[:MAX_WORDS]]
