"""Bound parameters of a hand-built statement: every value goes through `Params.bind`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import TextClause, bindparam, text
from sqlalchemy.types import TypeEngine


@dataclass(slots=True)
class Params:
    """Collects bind parameters under generated names; the SQL text only holds `:pN`."""

    _bound: list[Any] = field(default_factory=list)

    def bind(self, value: object, type_: TypeEngine | None = None) -> str:
        """Register `value` and return its placeholder, e.g. `:p3`."""
        name = f"p{len(self._bound)}"
        self._bound.append(bindparam(name, value, type_=type_))
        return f":{name}"

    def statement(self, sql: str) -> TextClause:
        """Turn `sql` into a statement with the registered parameters it uses attached."""
        used = set(re.findall(r":(p\d+)\b", sql))
        return text(sql).bindparams(*(b for b in self._bound if b.key in used))
