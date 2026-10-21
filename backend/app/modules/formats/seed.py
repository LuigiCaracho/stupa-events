"""The starter formats as rows: the migration `0006` and `ensure_formats` insert the same ones.

Ids are `uuid5` of the slug, so a second database or a second run yields the same rows and
an upsert stays idempotent. `organization` and `category` in `seeds/formats.yaml` are the
reference keys of `taxonomy/reference.py`.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

import yaml
from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.taxonomy.reference import reference_id

SEED_PATH = Path(__file__).resolve().parents[3] / "seeds" / "formats.yaml"
_NAMESPACE = uuid.UUID("0d8a7cf4-5d1e-4a1b-9f43-6b2d6a6f1e07")
INSERT_FORMAT = text(
    "INSERT INTO format (id, slug, title, organization_id, defaults, description_md, created_by)"
    " VALUES (:id, :slug, :title, :organization_id, CAST(:defaults AS jsonb), :description_md,"
    " 'system:seed') ON CONFLICT (slug) DO NOTHING"
)


def seed_rows(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    """Read the YAML file into insert parameters (the `defaults` as JSON text)."""
    import json

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["formats"]
    return [
        {
            "id": uuid.uuid5(_NAMESPACE, entry["slug"]),
            "slug": entry["slug"],
            "title": entry["title"],
            "organization_id": reference_id("organization", entry["organization"]),
            "defaults": json.dumps(
                {
                    "categoryId": str(reference_id("category", entry["category"])),
                    "durationMinutes": entry["durationMinutes"],
                    "checklistProfile": entry["checklistProfile"],
                }
            ),
            "description_md": entry["description"],
        }
        for entry in raw
    ]


async def ensure_formats(session: AsyncSession) -> int:
    """Insert the missing starter formats; return how many were new."""
    created = 0
    for row in seed_rows():
        created += cast("CursorResult", await session.execute(INSERT_FORMAT, row)).rowcount or 0
    return created
