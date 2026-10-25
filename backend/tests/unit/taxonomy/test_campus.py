"""The campus seed file: pinned by hash, well-formed, with building 9, and the centroid maths."""

from __future__ import annotations

import hashlib
import json

import pytest

from app.modules.taxonomy.campus import SEED_FILE, campus_rows, centroid

SEED_SHA256 = "cded57fbc002376cb6e842bd3ad9e8c456c01dfe6edc27409076cdf39caea1da"
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}


def test_the_seed_file_is_pinned() -> None:
    assert hashlib.sha256(SEED_FILE.read_bytes()).hexdigest() == SEED_SHA256


def test_building_nine_is_there_and_closed() -> None:
    rows = {r["number"]: r for r in campus_rows()}
    nine = rows["9"]
    ring = json.loads(nine["geometry"])["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) > 4
    assert nine["osm_ref"] == "way/290446675" and nine["approx"] is False


def test_every_polygon_lies_on_the_campus_and_numbers_are_unique() -> None:
    rows = campus_rows()
    assert len({r["number"] for r in rows}) == len(rows) >= 7
    for row in rows:
        lon, lat = centroid(json.loads(row["geometry"]))
        assert 9.17 < lon < 9.20 and 48.47 < lat < 48.49, row["number"]


def test_rows_are_ordered_by_number() -> None:
    assert [r["number"] for r in campus_rows()][:3] == ["1", "2", "3"]


def test_the_centroid_of_a_square_is_its_middle() -> None:
    assert centroid(SQUARE) == (1.0, 1.0)


def test_the_orientation_does_not_matter() -> None:
    clockwise = {"type": "Polygon", "coordinates": [SQUARE["coordinates"][0][::-1]]}
    assert centroid(clockwise) == (1.0, 1.0)


def test_a_multipolygon_weighs_by_area() -> None:
    big = SQUARE["coordinates"]
    small = [[[10, 0], [11, 0], [11, 1], [10, 1], [10, 0]]]
    lon, _ = centroid({"type": "MultiPolygon", "coordinates": [big, small]})
    assert lon == pytest.approx((4 * 1 + 1 * 10.5) / 5, abs=1e-6)


def test_a_degenerate_polygon_is_refused() -> None:
    flat = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [2, 0], [0, 0]]]}
    with pytest.raises(ValueError, match="degenerate"):
        centroid(flat)
