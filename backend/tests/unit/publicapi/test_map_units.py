"""Map units: the bounding box parser and the allowlist of the map models."""

from __future__ import annotations

import pytest

from app.modules.publicapi.map_router import parse_bbox
from app.shared.errors import ValidationProblem


def test_a_bbox_is_four_ordered_numbers() -> None:
    assert parse_bbox("9.1,48.4,9.3,48.6") == (9.1, 48.4, 9.3, 48.6)
    assert parse_bbox(None) is None


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "1,2,3",
        "a,b,c,d",
        "9.3,48.4,9.1,48.6",
        "-181,0,0,1",
        "0,-91,1,0",
        "0,0,1,91",
        "1,2,3,4,5",
    ],
)
def test_a_malformed_bbox_is_a_422(raw: str) -> None:
    with pytest.raises(ValidationProblem):
        parse_bbox(raw)
