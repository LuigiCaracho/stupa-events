"""Wire shapes of the internal search (I20): hits with segments, facets and a suggestion."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.modules.auth.schemas import CamelModel
from app.modules.formats.schemas import FormatRef
from app.modules.search.segments import Highlight


class OrgShort(CamelModel):
    """The slug and the short name of an organization."""

    slug: str
    short: str


class SearchHit(CamelModel):
    """One hit of a dossier, a document or a format."""

    kind: Literal["event", "document", "format"]
    id: UUID
    title: str
    subtitle: str
    state: str | None = None
    starts_at: datetime | None = None
    organization: OrgShort | None
    format: FormatRef | None
    howto_verified_at: datetime | None = None
    howto_unverified: bool | None = None
    foreign: bool
    link: str
    rank: float
    highlights: list[Highlight]


class FacetValue(CamelModel):
    """A facet value with the number of hits it covers."""

    value: str
    label: str
    count: int


class Facets(CamelModel):
    """The facets of the hit set, the top 20 values of each."""

    state: list[FacetValue]
    organization: list[FacetValue]
    year: list[FacetValue]
    category: list[FacetValue]
    format: list[FacetValue]


class SearchOut(CamelModel):
    """The answer of `GET /api/search`."""

    q: str
    scope: Literal["events", "documents", "formats"]
    total: int
    hits: list[SearchHit]
    facets: Facets
    suggestion: str | None
