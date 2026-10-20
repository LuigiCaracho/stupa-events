"""Line diff between two texts: `difflib.SequenceMatcher` over `splitlines()`."""

from __future__ import annotations

from difflib import SequenceMatcher

from app.modules.dossier.schemas_documents import DiffLine
from app.shared.errors import ValidationProblem

MAX_DIFF_LINES = 2000


def diff_lines(old: str, new: str) -> list[DiffLine]:
    """Return the diff as equal, add and remove lines with 1-based line numbers.

    Raises:
        ValidationProblem: 422 `diff_too_large` when either side has more than 2000 lines.
    """
    a, b = old.splitlines(), new.splitlines()
    if len(a) > MAX_DIFF_LINES or len(b) > MAX_DIFF_LINES:
        raise ValidationProblem("The texts are too long to compare.", code="diff_too_large")
    out: list[DiffLine] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [
                DiffLine(op="equal", text=a[i], from_line=i + 1, to_line=j1 + i - i1 + 1)
                for i in range(i1, i2)
            ]
            continue
        out += [
            DiffLine(op="remove", text=a[i], from_line=i + 1, to_line=None) for i in range(i1, i2)
        ]
        out += [DiffLine(op="add", text=b[j], from_line=None, to_line=j + 1) for j in range(j1, j2)]
    return out
