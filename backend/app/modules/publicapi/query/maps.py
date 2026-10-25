"""Map queries on `public_event_v` and `public_campus_building_v`.

The view rounds the coordinates by the venue's precision, so a row here carries what the
public may see and nothing else. Events come as points; campus buildings come as stored
polygons with the number of events in the asked range (cancelled ones do not count).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi.map_schemas import (
    PublicCampusCollection,
    PublicCampusFeature,
    PublicCampusProperties,
    PublicMapCollection,
    PublicMapFeature,
    PublicMapProperties,
    PublicPoint,
)
from app.modules.publicapi.query.cards import card_image
from app.modules.publicapi.query.filters import SiteFilters, where
from app.modules.search.params import Params

BBox = tuple[float, float, float, float]
MAP_COLUMNS = (
    "id, slug, title, starts_at, ends_at, public_status, category_slug, hero_sha, "
    "hero_derivatives, hero_alt, venue_name, venue_lat, venue_lon, venue_geo_precision"
)


def _bbox(box: BBox | None, params: Params) -> str:
    if box is None:
        return ""
    west, south, east, north = (params.bind(v, Float) for v in box)
    return f" AND venue_lon BETWEEN {west} AND {east} AND venue_lat BETWEEN {south} AND {north}"


def _feature(row: Row[Any]) -> PublicMapFeature:
    image = card_image(row)
    return PublicMapFeature(
        geometry=PublicPoint(coordinates=(row.venue_lon, row.venue_lat)),
        properties=PublicMapProperties(
            slug=row.slug,
            title=row.title,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            status=row.public_status,
            category_slug=row.category_slug,
            image_thumb=image.url if image else None,
            venue_name=row.venue_name,
            precision=row.venue_geo_precision,
        ),
    )


async def events(
    session: AsyncSession, filters: SiteFilters, box: BBox | None, limit: int, now: datetime
) -> PublicMapCollection:
    """Read the events with a public coordinate, soonest first (newest first for `past`)."""
    params = Params()
    condition = where(filters, params, [])
    order = "DESC" if filters.descending else "ASC"
    sql = (
        f"SELECT {MAP_COLUMNS} FROM public_event_v WHERE {condition}"
        f" AND venue_lat IS NOT NULL AND venue_lon IS NOT NULL{_bbox(box, params)}"
        f" ORDER BY starts_at {order}, id {order} LIMIT {limit + 1}"
    )
    rows = (await session.execute(params.statement(sql))).all()
    return PublicMapCollection(
        generated_at=now,
        truncated=len(rows) > limit,
        features=[_feature(r) for r in rows[:limit]],
    )


async def campus(
    session: AsyncSession, filters: SiteFilters, now: datetime
) -> PublicCampusCollection:
    """Read every building polygon with the number of events in the range of `filters`."""
    params = Params()
    condition = where(filters, params, [])
    counts_sql = (
        "SELECT venue_building_no AS number, count(*) AS n FROM public_event_v"
        f" WHERE {condition} AND venue_building_no IS NOT NULL AND public_status <> 'cancelled'"
        " GROUP BY venue_building_no"
    )
    counts = {r.number: r.n for r in (await session.execute(params.statement(counts_sql))).all()}
    buildings = (
        await session.execute(
            params.statement(
                "SELECT number, name, geometry, approx FROM public_campus_building_v"
                " ORDER BY sort, number"
            )
        )
    ).all()
    return PublicCampusCollection(
        generated_at=now,
        features=[
            PublicCampusFeature(
                geometry=b.geometry,
                properties=PublicCampusProperties(
                    building_no=b.number,
                    name=b.name,
                    approx=b.approx,
                    count=counts.get(b.number, 0),
                ),
            )
            for b in buildings
        ],
    )
