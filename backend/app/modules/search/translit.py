"""German transliteration for the search: "Huettencafe" finds "Hüttencafé" (contract 6.2).

`unaccent` folds umlauts to one letter ("ü" to "u"), while people type "ue". The query
therefore carries both spellings: the typed one and this folded one.
"""

from __future__ import annotations

import re

_DIGRAPH = re.compile(r"([aouAOU])[eE]")


def translit(text: str) -> str:
    """Fold the digraphs ae, oe and ue to a, o and u (case kept, ß left to `unaccent`)."""
    return _DIGRAPH.sub(lambda m: m.group(1), text)
