"""Turn a `ts_headline` result into segments without HTML (contract 6.1).

The database marks hits with the control characters `chr(1)` and `chr(2)`. The server cuts
the text there, so the client renders `<mark>` from plain text and never uses `innerHTML`.
A title is highlighted whole (`HighlightAll`): a fragment would cut its tail ("(OmU)").
"""

from __future__ import annotations

from app.modules.auth.schemas import CamelModel

START, STOP = "\x01", "\x02"
HEADLINE_OPTIONS = f"StartSel={START},StopSel={STOP},MaxFragments=1,MaxWords=18,MinWords=6"
TITLE_HEADLINE_OPTIONS = f"StartSel={START},StopSel={STOP},HighlightAll=true"


class Segment(CamelModel):
    """A piece of text and whether it is a hit."""

    text: str
    hit: bool


class Highlight(CamelModel):
    """The segments of one field of a hit."""

    field: str
    segments: list[Segment]


def segments(marked: str) -> list[Segment]:
    """Cut `marked` at the start and stop marks; empty pieces are dropped."""
    head, *marked_chunks = marked.split(START)
    pieces = [Segment(text=head, hit=False)]
    for chunk in marked_chunks:
        hit, _, rest = chunk.partition(STOP)
        pieces += [Segment(text=hit, hit=True), Segment(text=rest, hit=False)]
    return [piece for piece in pieces if piece.text]


def highlight(field: str, marked: str | None) -> Highlight | None:
    """Build the highlight of a field, or `None` when the text has no hit."""
    if not marked or START not in marked:
        return None
    return Highlight(field=field, segments=segments(marked))
