"""The campus building polygons: loading `seeds/campus.geojson`, seeding the table, centroids.

`campus_building` holds one GeoJSON polygon per building number. The seed file comes from a
one-off OpenStreetMap check (`docs/C-CAMPUS-OSM.md`, © OpenStreetMap contributors, ODbL); the
API reads only the table, never OSM. `seed_campus` inserts what is missing and leaves existing
rows alone, so a later correction is a new migration. `centroid` is the plain area centroid
of the outer rings, used to pin the venues of a building.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

SEED_FILE = Path(__file__).resolve().parents[3] / "seeds" / "campus.geojson"
_INSERT = sa.text(
    "INSERT INTO campus_building (number, name, geometry, approx, osm_ref, sort) "
    "VALUES (:number, :name, CAST(:geometry AS jsonb), :approx, :osm_ref, :sort) "
    "ON CONFLICT (number) DO NOTHING"
)
Ring = list[list[float]]


def campus_rows(path: Path = SEED_FILE) -> list[dict[str, Any]]:
    """Read the seed file into rows of `campus_building`, ordered by building number."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        {
            "number": feature["properties"]["number"],
            "name": feature["properties"]["name"],
            "geometry": json.dumps(feature["geometry"], separators=(",", ":")),
            "approx": bool(feature["properties"].get("approx", False)),
            "osm_ref": feature["properties"].get("osmRef"),
            "sort": 0,
        }
        for feature in collection["features"]
    ]
    rows.sort(key=lambda r: (len(r["number"].rstrip("abcdefghijklmnopqrstuvwxyz")), r["number"]))
    return [{**row, "sort": index} for index, row in enumerate(rows)]


def seed_campus(connection: Connection) -> int:
    """Insert the missing buildings; return how many rows the seed file holds."""
    rows = campus_rows()
    if rows:
        connection.execute(_INSERT, rows)
    return len(rows)


async def seed_campus_async(session: AsyncSession) -> int:
    """Run `seed_campus` on an async session."""
    return await session.run_sync(lambda sync: seed_campus(sync.connection()))


def _ring_centroid(ring: Ring) -> tuple[float, float, float]:
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    sign = -1.0 if area < 0 else 1.0
    return sign * area / 2, sign * cx, sign * cy


def centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """Return the area centroid `(lon, lat)` of a Polygon or MultiPolygon, outer rings only."""
    polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else list(geometry["coordinates"])
    )
    parts = [_ring_centroid(polygon[0]) for polygon in polygons]
    total = sum(area for area, _, _ in parts)
    if total == 0:
        raise ValueError("degenerate polygon")
    lon = sum(cx for _, cx, _ in parts) / (6 * total)
    lat = sum(cy for _, _, cy in parts) / (6 * total)
    return round(lon, 6), round(lat, 6)
