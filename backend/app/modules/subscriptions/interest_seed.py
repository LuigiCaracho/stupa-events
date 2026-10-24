"""The questionnaire interests as rows: migration `0009` inserts exactly these.

Category ids are `uuid5` of the slug (`taxonomy.reference`), so a seed run on any database
yields the same ids. `seeds/interests.yaml` holds the slugs, never ids.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.modules.taxonomy.reference import reference_id

SEED_PATH = Path(__file__).resolve().parents[3] / "seeds" / "interests.yaml"


def seed_rows(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    """Read the YAML file into insert parameters."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["interests"]
    return [
        {
            "slug": entry["slug"],
            "label": entry["label"],
            "category_ids": [reference_id("category", slug) for slug in entry["categories"]],
            "sort": entry["sort"],
        }
        for entry in raw
    ]
