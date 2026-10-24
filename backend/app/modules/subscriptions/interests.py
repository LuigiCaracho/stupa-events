"""Interests to categories: the pure resolution and the catalog read from the database.

The questionnaire has five questions; its answers become a list of interest slugs (the
meetings question adds `sitzung`, the faculty question adds `fachschaft:<slug>`) and then a
list of category slugs: every category of every interest plus its child categories, at most 40.
`interest.category_ids` holds the `uuid5` ids of `taxonomy.reference`, so the catalog maps
them back to slugs without reading the `category` table (the role sees only the public views).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.taxonomy.reference import reference_id

MAX_CATEGORIES: Final = 40
FACULTY_PREFIX: Final = "fachschaft:"
_FACULTY_CATEGORY_PREFIX: Final = "fachschaft-"
MEETINGS: Final = "sitzung"


class UnknownInterestError(ValueError):
    """An answer names an interest that does not exist."""


class NoInterestError(ValueError):
    """The answers resolve to no category at all."""


class TooManyCategoriesError(ValueError):
    """The answers resolve to more than `MAX_CATEGORIES` categories."""


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    """A public category as the subscription code needs it."""

    slug: str
    name: str
    kind: str
    parent_slug: str | None


@dataclass(frozen=True, slots=True)
class InterestInfo:
    """A questionnaire chip and the category slugs it stands for."""

    slug: str
    label: str
    category_slugs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Resolution:
    """The answers as stored: interest slugs and the categories they resolve to."""

    interests: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Catalog:
    """Active interests and categories, read once per request."""

    interests: Mapping[str, InterestInfo]
    categories: Mapping[str, CategoryInfo]

    def faculties(self) -> dict[str, CategoryInfo]:
        """Return the faculty options: `fachschaft:<short slug>` to the child category."""
        return {
            faculty_value(c.slug): c
            for c in self.categories.values()
            if c.kind == "fachschaft" and c.parent_slug is not None
        }

    def label(self, interest: str) -> str:
        """Return the chip label of an interest slug, faculty values included."""
        if interest in self.interests:
            return self.interests[interest].label
        return self.faculties()[interest].name


def faculty_value(category_slug: str) -> str:
    """Return the interest value of a faculty category (`fachschaft-fsi` gives `fachschaft:fsi`)."""
    return FACULTY_PREFIX + category_slug.removeprefix(_FACULTY_CATEGORY_PREFIX)


def _descendants(slug: str, categories: Mapping[str, CategoryInfo]) -> list[str]:
    found = [slug]
    for child in (c.slug for c in categories.values() if c.parent_slug == slug):
        found.extend(_descendants(child, categories))
    return found


def resolve_categories(
    catalog: Catalog, interests: Sequence[str], meetings: bool, faculty: str | None
) -> Resolution:
    """Resolve questionnaire answers to interests and categories.

    Args:
        catalog: The active interests and categories.
        interests: Chosen interest slugs; `fachschaft:<slug>` values are allowed too.
        meetings: Whether the person wants meetings (adds `sitzung`).
        faculty: A `fachschaft:<slug>` value or `None`.

    Raises:
        UnknownInterestError: An entry is neither an interest nor a faculty option.
        NoInterestError: Nothing was chosen, or nothing chosen resolves to an active category.
        TooManyCategoriesError: More than 40 categories result.
    """
    chosen = list(
        dict.fromkeys(
            [*interests, *([MEETINGS] if meetings else []), *([faculty] if faculty else [])]
        )
    )
    faculties = catalog.faculties()
    for entry in chosen:
        if entry not in catalog.interests and entry not in faculties:
            raise UnknownInterestError(entry)
    if not chosen:
        raise NoInterestError
    slugs: list[str] = []
    for entry in chosen:
        roots = (
            [faculties[entry].slug]
            if entry in faculties
            else [s for s in catalog.interests[entry].category_slugs if s in catalog.categories]
        )
        for root in roots:
            slugs.extend(_descendants(root, catalog.categories))
    categories = tuple(dict.fromkeys(slugs))
    if not categories:
        raise NoInterestError
    if len(categories) > MAX_CATEGORIES:
        raise TooManyCategoriesError
    return Resolution(tuple(chosen), categories)


async def load_catalog(session: AsyncSession) -> Catalog:
    """Read the active interests and the active public categories."""
    categories = {
        row.slug: CategoryInfo(row.slug, row.name, row.kind, row.parent_slug)
        for row in await session.execute(
            text(
                "SELECT slug, name, kind, parent_slug FROM public_category_v "
                "WHERE active ORDER BY sort, slug"
            )
        )
    }
    by_id = {reference_id("category", slug): slug for slug in categories}
    interests = {
        row.slug: InterestInfo(
            row.slug, row.label, tuple(by_id[i] for i in row.category_ids if i in by_id)
        )
        for row in await session.execute(
            text("SELECT slug, label, category_ids FROM interest WHERE active ORDER BY sort, slug")
        )
    }
    return Catalog(interests, categories)
