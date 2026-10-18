"""Reference data of the platform: organizations and categories (KARTE 2.3, 2.6, 9).

The ids are `uuid5` of the slug, so a seed run on any database yields the same ids and
migration `0002_events_core` and `scripts/seed_dev.py` can share this module. A category
is never deleted, only deactivated. `legacy_wp_id` keeps the id of the old WordPress term.
"""

from __future__ import annotations

from typing import Any, Final
from uuid import NAMESPACE_URL, UUID, uuid5

_NAMESPACE: Final = uuid5(NAMESPACE_URL, "https://stupa-events.invalid/reference")


def reference_id(kind: str, slug: str) -> UUID:
    """Return the stable id of the reference row `kind`/`slug`."""
    return uuid5(_NAMESPACE, f"{kind}:{slug}")


def _category(
    slug: str,
    name: str,
    kind: str,
    legacy: int | None = None,
    *,
    parent: str | None = None,
    short: str | None = None,
    color: str | None = None,
    profile: str = "generic",
) -> dict[str, Any]:
    return {
        "id": reference_id("category", slug),
        "slug": slug,
        "name": name,
        "kind": kind,
        "parent_id": reference_id("category", parent) if parent else None,
        "short": short,
        "color_token": color,
        "required_profile": profile,
        "legacy_wp_id": legacy,
    }


CATEGORIES: Final[tuple[dict[str, Any], ...]] = (
    _category("kino", "Kino", "format", 150),
    _category("party", "Party", "format", 104, profile="party"),
    _category("sitzung", "Sitzung", "format", 166, profile="meeting"),
    _category("get-together", "Get-together", "format", 106),
    _category("campusfest", "Campusfest", "format", 103),
    _category("festival", "Festival", "format", 102),
    _category("konzert", "Konzert", "format", 169),
    _category("workshop", "Workshop", "format", 182),
    _category("lan-party", "LAN-Party", "format", 165),
    _category("ausfahrt", "Ausfahrt", "format", 136, profile="trip"),
    _category("skiausfahrt", "Skiausfahrt", "format", 147, profile="trip"),
    _category("skydiving", "Skydiving", "format", 112, profile="trip"),
    _category("kart-fahren", "Kart fahren", "format", 186),
    _category("repair-cafe", "Repair Café", "format", 181),
    _category("cooking-class", "Cooking Class", "format", 159),
    _category("fachschaft", "Fachschaft", "fachschaft", 138),
    _category(
        "fachschaft-fsi",
        "Fachschaft Informatik",
        "fachschaft",
        173,
        parent="fachschaft",
        short="FSI",
        color="petrol",
    ),
    _category(
        "fachschaft-tec",
        "Fachschaft Technik",
        "fachschaft",
        174,
        parent="fachschaft",
        short="TEC",
        color="red",
    ),
    _category(
        "fachschaft-tex",
        "Fachschaft Texoversum",
        "fachschaft",
        175,
        parent="fachschaft",
        short="TEX",
        color="yellow",
    ),
    _category(
        "fachschaft-ls",
        "Fachschaft Life Sciences",
        "fachschaft",
        parent="fachschaft",
        short="LS",
        color="orange",
    ),
    _category(
        "fachschaft-nxt",
        "Fachschaft NXT",
        "fachschaft",
        parent="fachschaft",
        short="NXT",
        color="blue",
    ),
    _category(
        "esb-stuco", "ESB StuCo", "fachschaft", parent="fachschaft", short="ESB", color="navy"
    ),
    _category("makers", "MAKERS", "partner", 178, short="MAKERS"),
    _category("oikos", "oikos", "partner", 160, short="oikos"),
    _category("care", "CaRe", "partner", 153, short="CaRe"),
    _category("ekhg", "ekhg", "partner", short="ekhg"),
    _category("hochschule", "Hochschule Reutlingen", "partner", short="HSRT"),
)


def _organization(
    slug: str,
    name: str,
    kind: str,
    short: str,
    *,
    category: str | None = None,
    color: str | None = None,
    legacy: tuple[int, ...] = (),
    trusted: bool = False,
) -> dict[str, Any]:
    return {
        "id": reference_id("organization", slug),
        "slug": slug,
        "name": name,
        "kind": kind,
        "short": short,
        "category_id": reference_id("category", category) if category else None,
        "color_token": color,
        "legacy_wp_ids": list(legacy),
        "trusted": trusted,
    }


ORGANIZATIONS: Final[tuple[dict[str, Any], ...]] = (
    _organization("stupa", "Studierendenparlament", "stupa", "STUPA", legacy=(1578,), trusted=True),
    _organization("makers", "MAKERS", "referat", "MAKERS", category="makers", legacy=(2257,)),
    _organization(
        "fsi",
        "Fachschaft Informatik",
        "fachschaft",
        "FSI",
        category="fachschaft-fsi",
        color="petrol",
        legacy=(1649,),
    ),
    _organization(
        "tec",
        "Fachschaft Technik",
        "fachschaft",
        "TEC",
        category="fachschaft-tec",
        color="red",
        legacy=(174,),
    ),
    _organization(
        "tex",
        "Fachschaft Texoversum",
        "fachschaft",
        "TEX",
        category="fachschaft-tex",
        color="yellow",
        legacy=(1730,),
    ),
    _organization(
        "ls",
        "Fachschaft Life Sciences",
        "fachschaft",
        "LS",
        category="fachschaft-ls",
        color="orange",
        legacy=(2021,),
    ),
    _organization(
        "nxt", "Fachschaft NXT", "fachschaft", "NXT", category="fachschaft-nxt", color="blue"
    ),
    _organization(
        "esb-stuco", "ESB StuCo", "fachschaft", "ESB", category="esb-stuco", color="navy"
    ),
    _organization("ekhg", "ekhg", "partner", "ekhg", category="ekhg", legacy=(2695,)),
    _organization(
        "hochschule",
        "Hochschule Reutlingen",
        "hochschule",
        "HSRT",
        category="hochschule",
        legacy=(2709,),
    ),
    _organization("praesidium", "Präsidium", "hochschule", "Präsidium", legacy=(2566,)),
    _organization("oikos", "oikos", "partner", "oikos", category="oikos", legacy=(2007, 2017)),
    _organization("care", "CaRe", "partner", "CaRe", category="care", legacy=(1990,)),
)
