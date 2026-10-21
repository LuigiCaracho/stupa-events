"""Wire shapes of the library (I19): shared documents and files of archived dossiers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.modules.auth.schemas import CamelModel
from app.modules.search.schemas import FacetValue, OrgShort
from app.shared.paging import Page


class LibrarySource(CamelModel):
    """Where an item comes from: an archived dossier or a format (master howto)."""

    type: Literal["event", "format"]
    id: UUID
    title: str
    starts_at: datetime | None
    organization: OrgShort
    own: bool


class LibraryCategory(CamelModel):
    """The main category of the source dossier."""

    slug: str
    name: str


class LibraryItem(CamelModel):
    """A shared document or attachment; the list never carries a text."""

    kind: Literal["document", "attachment"]
    id: UUID
    title: str
    sub_kind: str
    source: LibrarySource
    categories: list[LibraryCategory]
    year: int | None
    verified_at: datetime | None
    updated_at: datetime
    mime: str | None = None
    size_bytes: int | None = None


class LibraryFacets(CamelModel):
    """The facets of the filtered set: category, organization, year and kind."""

    category: list[FacetValue]
    organization: list[FacetValue]
    year: list[FacetValue]
    kind: list[FacetValue]


class LibraryPage(Page[LibraryItem]):
    """One page of the library with the facets of the whole filtered set."""

    facets: LibraryFacets
