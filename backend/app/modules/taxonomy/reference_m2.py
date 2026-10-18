"""Reference changes of M2 as data (contract 3.3); `reference.py` and `0002` stay untouched.

The ids stay `uuid5` of the M1 key, so existing rows and foreign keys keep their ids. The
category slugs follow the WordPress archive (KARTE 9: "existing slugs and URLs stay"),
and the organization `tec` loses the category id 174 in `legacy_wp_ids`.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from app.modules.taxonomy.reference import reference_id

CATEGORY_SLUG_RENAMES: Final[tuple[tuple[str, str], ...]] = (
    ("lan-party", "lanparty"),
    ("fachschaft-fsi", "fachschaft-informatik-fsi"),
    ("fachschaft-tec", "fachschaft-technik-tec"),
    ("fachschaft-tex", "fachschaft-texoversum-tex"),
    ("fachschaft-ls", "fachschaft-life-sciences-ls"),
)
ORGANIZATION_LEGACY_FIXES: Final[tuple[tuple[str, tuple[int, ...]], ...]] = (("tec", ()),)


def category_renames() -> list[tuple[UUID, str]]:
    """Return `(id, new slug)` of every renamed category."""
    return [(reference_id("category", old), new) for old, new in CATEGORY_SLUG_RENAMES]


def organization_legacy_fixes() -> list[tuple[UUID, list[int]]]:
    """Return `(id, legacy_wp_ids)` of every organization whose WordPress ids change."""
    return [
        (reference_id("organization", slug), list(ids)) for slug, ids in ORGANIZATION_LEGACY_FIXES
    ]
