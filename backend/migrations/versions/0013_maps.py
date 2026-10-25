"""Maps: `geocode_cache`, `campus_building`, coordinates and building number on `public_event_v`.

Revision ID: 0013_maps
Revises: 0012_purge_rearmed
Create Date: 2026-10-25 00:00:13

The view `public_event_v` gets four columns at the end (`venue_lat`, `venue_lon`,
`venue_geo_precision`, `venue_building_no`). Rounding to three decimals for the precision
`building` happens here, in the one place that decides what is public; a private venue, a
`hidden` one and a free-text location never carry a coordinate. `public_campus_building_v`
shows the building polygons to the public role. The downgrade drops both views and restores
the view of migration 0008 (Postgres cannot remove a column with `CREATE OR REPLACE`).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic import op

from app.modules.events.models import CONTROL_CHARS
from app.modules.taxonomy.campus import seed_campus

revision: str = "0013_maps"
down_revision: str | None = "0012_purge_rearmed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VISIBLE = "v.id IS NOT NULL AND NOT v.is_private AND v.lat IS NOT NULL"
_COLUMNS = f"""
       CASE WHEN {_VISIBLE} AND v.public_precision = 'exact' THEN v.lat::float8
            WHEN {_VISIBLE} AND v.public_precision = 'building' THEN round(v.lat, 3)::float8
       END AS venue_lat,
       CASE WHEN {_VISIBLE} AND v.public_precision = 'exact' THEN v.lon::float8
            WHEN {_VISIBLE} AND v.public_precision = 'building' THEN round(v.lon, 3)::float8
       END AS venue_lon,
       CASE WHEN {_VISIBLE} AND v.public_precision <> 'hidden'
            THEN v.public_precision END AS venue_geo_precision,
       CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.public_precision <> 'hidden'
            THEN v.building_no END AS venue_building_no
"""
_CAMPUS_VIEW = """
CREATE VIEW public_campus_building_v AS
SELECT number, name, geometry, approx, sort FROM campus_building
"""
_GRANT = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        GRANT SELECT ON public_event_v TO events_public;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_subs') THEN
            GRANT SELECT ON public_event_v TO events_subs;
        END IF;
        IF to_regclass('public.public_campus_building_v') IS NOT NULL THEN
            GRANT SELECT ON public_campus_building_v TO events_public;
        END IF;
    END IF;
END $$;
"""


def _migration_0008() -> ModuleType:
    path = Path(__file__).with_name("0008_public_site.py")
    spec = importlib.util.spec_from_file_location("migration_0008", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _view(*, replace: bool, extra: str = "") -> str:
    legacy = _migration_0008()
    sql: str = legacy._event_view(legacy._view_body(), replace=replace)
    assert "e.search_tsv\nFROM" in sql
    return sql.replace("e.search_tsv\nFROM", f"e.search_tsv,{extra}\nFROM") if extra else sql


def upgrade() -> None:
    op.create_table(
        "geocode_cache",
        sa.Column("query_hash", sa.Text(), primary_key=True),
        sa.Column("query_norm", sa.Text(), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lon", sa.Numeric(9, 6)),
        sa.Column("display_name", sa.Text()),
        sa.Column("osm_type", sa.Text()),
        sa.Column("osm_id", sa.BigInteger()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("found = (lat IS NOT NULL AND lon IS NOT NULL)", name="found_matches"),
        sa.CheckConstraint(
            f"char_length(query_norm) <= 300 AND query_norm !~ '{CONTROL_CHARS}'",
            name="query_clean",
        ),
    )
    op.create_table(
        "campus_building",
        sa.Column("number", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("geometry", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("approx", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("osm_ref", sa.Text()),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("number ~ '^[0-9]{1,3}[a-z]?$'", name="number_ok"),
        sa.CheckConstraint(
            "geometry ->> 'type' IN ('Polygon', 'MultiPolygon')", name="geometry_type"
        ),
        sa.CheckConstraint("NOT approx OR osm_ref IS NULL", name="approx_has_no_osm"),
    )
    seed_campus(op.get_bind())
    op.execute(_view(replace=True, extra=_COLUMNS))
    op.execute(_CAMPUS_VIEW)
    op.execute(_GRANT)


def downgrade() -> None:
    op.execute("DROP VIEW public_campus_building_v")
    op.execute("DROP VIEW public_event_v")
    op.execute(_view(replace=False))
    op.drop_table("campus_building")
    op.drop_table("geocode_cache")
    op.execute(_GRANT)
