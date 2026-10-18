"""The 44 venues of the WordPress archive (KARTE 2.5, `wp-live.md` 3.8).

An address is set only where the source names it; nothing is researched. `lat` and `lon`
stay empty and `public_precision` stays `hidden` until stage C curates them. The ids are
`uuid5` of the slug (`reference_id("venue", slug)`) and `legacy_wp_id` is the post id of
the old `tribe_venue`. Slugs fix the typos of the old archive, unlike the category slugs
(deviation 10 of M2-KONTRAKT section 10). Migration 0003 imports this data; the hash test in
`tests/unit/taxonomy/test_reference_data.py` pins it.
"""

from __future__ import annotations

from typing import Any, Final

from app.modules.taxonomy.reference import reference_id
from app.modules.taxonomy.venues import building_of, normalize_room_key, slugify

_PESTALOZZI: Final = {"city": "Reutlingen"}
_ALTEBURG: Final = {"address": "Alteburgstraße 150", "city": "Reutlingen"}

_ROWS: Final[tuple[tuple[int, str, dict[str, Any]], ...]] = (
    (
        1932,
        "Kinosaal 9-133",
        {"address": "Pestalozzistraße 62", "postcode": "72762", **_PESTALOZZI},
    ),
    (1648, "Fakultät Informatik", {"address": "Pestalozzistraße 62", **_PESTALOZZI}),
    (2006, "Students Hut", {"address": "Pestalozzistraße 52", **_PESTALOZZI}),
    (2565, "Präsidium Gebäude 3", _ALTEBURG),
    (2377, "Maker Space 9-229", {}),
    (2059, "FSI 9-U09", {}),
    (1639, "Hochschule Reutlingen", _ALTEBURG),
    (
        2322,
        "Texoversum",
        {
            "address": "Alteburgstraße",
            "city": "Reutlingen",
            "building_no": "30",
            "notes": "Source names Building 30 without a house number.",
        },
    ),
    (2319, "Stupa Büro", {}),
    (
        2277,
        "Zum alten Rappen",
        {"address": "Ob. Gerberstraße 6", "notes": "Source names no town."},
    ),
    (1595, "JAZZclub in der Mitte", {}),
    (2032, "Senatssaal", {"notes": "Raum 5003"}),
    (2433, "Raum 5-015", {}),
    (2355, "Raum 17-U14", {}),
    (2411, "Campus Reutlingen Building 17", {}),
    (2367, "Geb. 17 Pavillon", {}),
    (1989, "Aula Building 6", {"slug": "aula"}),
    (1981, "Maschinenhalle Geb. 1", {}),
    (2363, "Rasen zwischen Geb. 3 und Geb. 1", {}),
    (2648, "Davos", {}),
    (2645, "Schwarzwald", {}),
    (2642, "Serfaus-Fiss-Ladis", {"address": "Gänsackerweg 2", "city": "Serfaus"}),
    (2639, "Arosa-Lenzerheide", {}),
    (1813, "Flumserberg", {}),
    (1810, "Montafon", {}),
    (1805, "Ischgl", {}),
    (2579, "Rosengarten Pomologie", {"address": "Friedrich-Ebert-Straße 12", **_PESTALOZZI}),
    (2441, "Kart & Fun Neckartenzlingen", {}),
    (2393, "Europapark", {"city": "Rust"}),
    (2390, "in the air", {}),
    (2386, "Am Kreuzeichenstadion", {}),
    (2382, "Göckelesmaier Festzelt", {"notes": "Cannstatter Wasen"}),
    (2198, "Hades", {}),
    (2056, "franz.K", {}),
    (2020, "Arcadia", {}),
    (2000, "Schwarzen Schaf", {"city": "Tübingen"}),
    (1796, "Jugend-Hüttendorf Vulkaneifel", {}),
    (1729, "The mad coyote", {}),
    (1643, "Straßburg", {}),
    (1632, "Eishalle Reutlingen", {}),
    (1625, "Jugenddorf Teufelsfels", {}),
    (1621, "Festzelt Fürstenberg", {}),
    (1612, "FSC Calw e.V.", {}),
    (1579, "Extrial Campusfest 2025", {}),
)


def _venue(legacy: int, name: str, extra: dict[str, Any]) -> dict[str, Any]:
    slug = extra.get("slug") or slugify(name)
    room = normalize_room_key(name.removeprefix("Raum ").rsplit(" ", 1)[-1])
    return {
        "id": reference_id("venue", slug),
        "slug": slug,
        "name": name,
        "address": None,
        "postcode": None,
        "city": None,
        "building_no": building_of(name),
        "room_key": room,
        "notes": None,
        "legacy_wp_id": legacy,
        **{k: v for k, v in extra.items() if k != "slug"},
    }


VENUES: Final[tuple[dict[str, Any], ...]] = tuple(_venue(*row) for row in _ROWS)
