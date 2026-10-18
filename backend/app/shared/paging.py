"""Uniform offset paging.

`PageParams` holds the query defaults. `Page[T]` wraps the response.

Copied from STUPA-Workflow@93c33d6 backend/app/shared/paging.py
"""

from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class PageParams(BaseModel):
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
