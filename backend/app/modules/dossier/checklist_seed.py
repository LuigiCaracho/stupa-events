"""Reads `seeds/checklists.yaml` into the rows of the template tables.

Ids are uuid5 of the slug and the item key, so a second run (or a second database) yields
the same rows and an upsert stays idempotent. A template with `extends` starts with the
items of the parent; items with the same key override the parent's.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml

SEED_PATH = Path(__file__).resolve().parents[3] / "seeds" / "checklists.yaml"
_NAMESPACE = uuid.UUID("6f1d4f0e-6a55-4a53-9a58-0c1c2b6a9f10")


def _merged(raw: dict[str, Any], slug: str) -> list[dict[str, Any]]:
    entry = raw[slug]
    inherited = _merged(raw, entry["extends"]) if "extends" in entry else []
    own = {item["key"]: item for item in entry["items"]}
    return [i for i in inherited if i["key"] not in own] + list(own.values())


def read_seed(path: Path = SEED_PATH) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return `(template_rows, item_rows)` ready for `INSERT ... ON CONFLICT DO NOTHING`."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    templates: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for slug, entry in raw.items():
        template_id = uuid.uuid5(_NAMESPACE, slug)
        templates.append(
            {"id": template_id, "slug": slug, "name": entry["name"], "profile": entry["profile"]}
        )
        items.extend(
            {
                "id": uuid.uuid5(_NAMESPACE, f"{slug}/{item['key']}"),
                "template_id": template_id,
                "key": item["key"],
                "position": position,
                "text": item["text"],
                "phase": item["phase"],
                "required": item["required"],
                "due_offset_days": item["offset"],
            }
            for position, item in enumerate(_merged(raw, slug))
        )
    return templates, items
