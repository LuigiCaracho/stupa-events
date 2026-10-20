"""Wire shapes of the account notification settings (camelCase)."""

from __future__ import annotations

from pydantic import Field

from app.modules.auth.schemas import CamelModel


class PrefOut(CamelModel):
    """The channel switches of one kind."""

    kind: str
    in_app: bool
    mail: bool
    mail_available: bool
    essential: bool


class PrefsOut(CamelModel):
    """The switches for all kinds."""

    items: list[PrefOut]


class PrefIn(CamelModel):
    """A change of one kind."""

    kind: str = Field(max_length=64)
    in_app: bool
    mail: bool


class PrefsIn(CamelModel):
    """A change of some kinds (a subset is allowed)."""

    items: list[PrefIn] = Field(max_length=32)
