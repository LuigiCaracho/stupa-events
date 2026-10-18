"""Static check: no module of the app calls `eval`, `exec`, `compile` or `__import__`."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parents[2]
_FILES = sorted(p for d in ("app", "worker") for p in (_APP / d).rglob("*.py"))
_FORBIDDEN = {"eval", "exec", "compile", "__import__"}


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.relative_to(_APP).as_posix())
def test_no_eval_or_exec_call(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FORBIDDEN
    ]
    assert not bad, f"{path.name} uses forbidden call(s): {bad}"
