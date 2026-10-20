"""The `meta` of an attachment per kind (PLAN 3.4): a closed Pydantic model, `extra=forbid`.

`poster` holds the format and the pixel size, `social_post` the planned post, `business_plan`
the plan totals, every other kind a short note. Quotes keep their amounts in the table
`quote`, so their `meta` stays empty.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, ValidationError

from app.modules.auth.schemas import CamelModel
from app.shared.errors import FieldError, ValidationProblem


class PosterFileMeta(CamelModel):
    """Format and size of a poster file."""

    format: Literal["a3", "a4", "1:1", "4:5", "9:16"] | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class SocialPostMeta(CamelModel):
    """A social media post planned with the picture."""

    channel: str = Field(min_length=1, max_length=60)
    account: str | None = Field(default=None, max_length=120)
    caption_md: str | None = Field(default=None, max_length=2200)
    planned_for: datetime | None = None
    posted_url: str | None = Field(default=None, max_length=500)
    status: Literal["draft", "planned", "posted"] = "draft"


class BusinessPlanMeta(CamelModel):
    """Totals of a business plan."""

    version: str | None = Field(default=None, max_length=40)
    total_cents: int | None = Field(default=None, ge=0)
    income_cents: int | None = Field(default=None, ge=0)


class NoteMeta(CamelModel):
    """A short note on a file."""

    note: str | None = Field(default=None, max_length=500)


class EmptyMeta(CamelModel):
    """No metadata at all."""


_MODELS: dict[str, type[CamelModel]] = {
    "poster": PosterFileMeta,
    "social_post": SocialPostMeta,
    "business_plan": BusinessPlanMeta,
    "quote": EmptyMeta,
}


def parse_meta(kind: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate `raw` against the meta model of `kind` and return the stored dict.

    Raises:
        ValidationProblem: 422 with one field error per violation.
    """
    model = _MODELS.get(kind, NoteMeta)
    try:
        return model.model_validate(raw or {}).model_dump(
            by_alias=True, mode="json", exclude_none=True
        )
    except ValidationError as exc:
        raise ValidationProblem(
            "Invalid attachment metadata.",
            errors=[
                FieldError(field=".".join(map(str, e["loc"])), msg=e["msg"]) for e in exc.errors()
            ],
        ) from exc
