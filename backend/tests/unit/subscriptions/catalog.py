"""A catalog built from the reference data and the interest seed, for the unit tests."""

from __future__ import annotations

from app.modules.subscriptions.interest_seed import seed_rows
from app.modules.subscriptions.interests import (
    Catalog,
    CategoryInfo,
    InterestInfo,
    category_ids_by_slug,
)
from app.modules.taxonomy.reference import CATEGORIES, reference_id
from app.modules.taxonomy.reference_m2 import CATEGORY_SLUG_RENAMES


def build_catalog(*, without: frozenset[str] = frozenset()) -> Catalog:
    """Return the seeded catalog; categories named in `without` are inactive."""
    renamed = {reference_id("category", old): new for old, new in CATEGORY_SLUG_RENAMES}
    slug_of = {c["id"]: renamed.get(c["id"], c["slug"]) for c in CATEGORIES}
    categories = {
        slug_of[c["id"]]: CategoryInfo(
            slug_of[c["id"]], c["name"], c["kind"], slug_of.get(c["parent_id"])
        )
        for c in CATEGORIES
        if slug_of[c["id"]] not in without
    }
    by_id = category_ids_by_slug(categories)
    interests = {
        row["slug"]: InterestInfo(
            row["slug"], row["label"], tuple(by_id[i] for i in row["category_ids"] if i in by_id)
        )
        for row in seed_rows()
    }
    return Catalog(interests, categories)
