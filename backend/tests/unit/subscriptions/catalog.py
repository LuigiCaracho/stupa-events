"""A catalog built from the reference data and the interest seed, for the unit tests."""

from __future__ import annotations

from app.modules.subscriptions.interest_seed import seed_rows
from app.modules.subscriptions.interests import Catalog, CategoryInfo, InterestInfo
from app.modules.taxonomy.reference import CATEGORIES, reference_id


def build_catalog(*, without: frozenset[str] = frozenset()) -> Catalog:
    """Return the seeded catalog; categories named in `without` are inactive."""
    categories = {
        c["slug"]: CategoryInfo(
            c["slug"],
            c["name"],
            c["kind"],
            next(
                (p["slug"] for p in CATEGORIES if p["id"] == c["parent_id"]),
                None,
            ),
        )
        for c in CATEGORIES
        if c["slug"] not in without
    }
    by_id = {reference_id("category", slug): slug for slug in categories}
    interests = {
        row["slug"]: InterestInfo(
            row["slug"], row["label"], tuple(by_id[i] for i in row["category_ids"] if i in by_id)
        )
        for row in seed_rows()
    }
    return Catalog(interests, categories)
