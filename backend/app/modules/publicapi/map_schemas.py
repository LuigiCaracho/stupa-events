"""The wire shapes of the map routes: events as points, campus buildings as polygons.

GeoJSON `FeatureCollection`s with camelCase properties, built field by field by
`query/maps.py`. A coordinate is already rounded by the view; no model here sees a raw
venue. Every field is named in `allowlist.PUBLIC_FIELDS`; `tests/schema/public-map-v1.json`
is the contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from app.modules.auth.schemas import CamelModel

Status = Literal["scheduled", "cancelled", "postponed"]
Precision = Literal["exact", "building"]


class PublicPoint(CamelModel):
    """A GeoJSON point, longitude first."""

    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class PublicMapProperties(CamelModel):
    """What a pin on the world map shows."""

    slug: str
    title: str
    starts_at: datetime
    ends_at: datetime
    status: Status
    category_slug: str | None
    image_thumb: str | None
    venue_name: str | None
    precision: Precision


class PublicMapFeature(CamelModel):
    """One event with a public coordinate."""

    type: Literal["Feature"] = "Feature"
    geometry: PublicPoint
    properties: PublicMapProperties


class PublicMapCollection(CamelModel):
    """The events of the world map; `truncated` tells that `limit` cut the list."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    generated_at: datetime
    truncated: bool
    features: list[PublicMapFeature]


class PublicCampusProperties(CamelModel):
    """A building of the campus map with the number of events in the asked range."""

    building_no: str
    name: str
    approx: bool
    count: int


class PublicCampusFeature(CamelModel):
    """One building polygon as stored (WGS84)."""

    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: PublicCampusProperties


class PublicCampusCollection(CamelModel):
    """All buildings, those without events included."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    generated_at: datetime
    features: list[PublicCampusFeature]
