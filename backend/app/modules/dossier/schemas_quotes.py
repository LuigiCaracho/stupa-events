"""Wire shapes of the comparison quotes."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel


class QuoteOut(CamelModel):
    """One quote of a comparison group."""

    id: UUID
    grp: str
    vendor: str
    amount_cents: int
    currency: str
    valid_until: date | None
    selected: bool
    note: str | None
    attachment_id: UUID | None
    expired: bool
    retired_at: datetime | None
    created_at: datetime


class QuoteGroupOut(CamelModel):
    """The quotes of one group with the cheapest and the selected one."""

    grp: str
    quotes: list[QuoteOut]
    cheapest_id: UUID | None
    selected_id: UUID | None


class CurrencyTotal(CamelModel):
    """A selected total in a currency other than the main one."""

    currency: str
    total_cents: int


class QuotesOut(CamelModel):
    """All groups plus the totals of the selected quotes."""

    groups: list[QuoteGroupOut]
    selected_total_cents: int
    selected_total_currency: str
    suggested_budget_cents: int
    other_currencies: list[CurrencyTotal]


class QuoteCreate(CamelModel):
    """Body of `POST /events/{id}/quotes`."""

    grp: str = Field(min_length=1, max_length=60)
    vendor: str = Field(min_length=1, max_length=120)
    amount_cents: int = Field(ge=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    valid_until: date | None = None
    note: str | None = Field(default=None, max_length=500)
    attachment_id: UUID | None = None


class QuotePatch(CamelModel):
    """Body of `PATCH /quotes/{id}`; the selection goes through `select`."""

    grp: str | None = Field(default=None, min_length=1, max_length=60)
    vendor: str | None = Field(default=None, min_length=1, max_length=120)
    amount_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    valid_until: date | None = None
    note: str | None = Field(default=None, max_length=500)
    attachment_id: UUID | None = None
