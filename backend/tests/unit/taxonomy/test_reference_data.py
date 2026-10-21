"""Reference data as code: 27 categories, 13 organizations, 44 venues, and the M2 changes."""

from __future__ import annotations

import hashlib
import json
import re

from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS, reference_id
from app.modules.taxonomy.reference_m2 import (
    CATEGORY_SLUG_RENAMES,
    category_renames,
    organization_legacy_fixes,
)
from app.modules.taxonomy.venue_reference import VENUES

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
SOURCE_ADDRESSES = {
    "Pestalozzistraße 62": {"kinosaal-9-133", "fakultaet-informatik"},
    "Pestalozzistraße 52": {"students-hut"},
    "Alteburgstraße 150": {"praesidium-gebaeude-3", "hochschule-reutlingen"},
    "Alteburgstraße": {"texoversum"},
    "Ob. Gerberstraße 6": {"zum-alten-rappen"},
    "Gänsackerweg 2": {"serfaus-fiss-ladis"},
    "Friedrich-Ebert-Straße 12": {"rosengarten-pomologie"},
}


KARTE_SLUGS = frozenset(
    {
        "ausfahrt", "campusfest", "care", "cooking-class", "fachschaft",
        "fachschaft-informatik-fsi", "fachschaft-technik-tec", "fachschaft-texoversum-tex",
        "festival", "get-together", "kart-fahren", "kino", "konzert", "lanparty", "makers",
        "oikos", "party", "repair-cafe", "sitzung", "skiausfahrt", "skydiving", "workshop",
    }
)  # fmt: skip
NEW_SLUGS = frozenset(
    {"fachschaft-life-sciences-ls", "fachschaft-nxt", "esb-stuco", "ekhg", "hochschule"}
)
VENUES_SHA256 = "06e6532b1ea9967b6876224ab13e5e200ba4a17baf34cf5d75ed11e5aeafe141"


def test_the_category_set_after_m2() -> None:
    renamed = dict(CATEGORY_SLUG_RENAMES)
    slugs = [renamed.get(c["slug"], c["slug"]) for c in CATEGORIES]
    assert len(slugs) == 27
    assert set(slugs) == KARTE_SLUGS | NEW_SLUGS


def test_the_venue_data_is_pinned_because_migration_0003_imports_it() -> None:
    canonical = json.dumps(VENUES, sort_keys=True, default=str).encode()
    assert hashlib.sha256(canonical).hexdigest() == VENUES_SHA256


def test_the_renames_keep_the_ids_of_the_m1_keys() -> None:
    assert [i for i, _ in category_renames()] == [
        reference_id("category", old) for old, _ in CATEGORY_SLUG_RENAMES
    ]
    assert all(SLUG.fullmatch(new) for _, new in category_renames())


def test_organizations_after_m2() -> None:
    assert len(ORGANIZATIONS) == 13
    assert all("trusted" not in o for o in ORGANIZATIONS)
    assert organization_legacy_fixes() == [(reference_id("organization", "tec"), [])]


def test_there_are_44_venues_with_unique_slugs_and_ids() -> None:
    assert len(VENUES) == 44
    assert len({v["slug"] for v in VENUES}) == 44
    assert len({v["id"] for v in VENUES}) == 44
    assert len({v["legacy_wp_id"] for v in VENUES}) == 44
    assert all(SLUG.fullmatch(v["slug"]) for v in VENUES)


def test_the_typos_of_the_archive_are_cleaned() -> None:
    slugs = {v["slug"] for v in VENUES}
    assert {"kinosaal-9-133", "maschinenhalle-geb-1", "aula"} <= slugs
    assert not {"kinosaal-9-113", "maschienenhalle-geb-1"} & slugs
    assert any(s.startswith("rasen-zwischen-geb-3") for s in slugs)


def test_addresses_come_only_from_the_source() -> None:
    expected = {slug: address for address, slugs in SOURCE_ADDRESSES.items() for slug in slugs}
    actual = {v["slug"]: v["address"] for v in VENUES if v["address"]}
    assert actual == expected


def test_derived_keys_and_the_missing_coordinates() -> None:
    by_slug = {v["slug"]: v for v in VENUES}
    assert by_slug["fsi-9-u09"]["room_key"] == "9-u9"
    assert by_slug["fsi-9-u09"]["building_no"] == "9"
    assert by_slug["senatssaal"]["room_key"] is None
    assert all("lat" not in v and "lon" not in v for v in VENUES)
