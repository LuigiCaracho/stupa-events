"""Roles and taxonomy: `venue`, `membership` and the reference changes of M2.

Revision ID: 0003_roles_taxonomy
Revises: 0002_events_core
Create Date: 2026-10-18 00:00:03

It creates `venue` (44 rows from `venue_reference`) and `membership`, and it is not purely
additive: it renames five category slugs (deviation D3, M2-KONTRAKT section 10, which
changes feed filters such as `?category=lan-party`) and clears the category id from
`organization.tec.legacy_wp_ids`. Rows keep their ids. The renames, the fix and the
constraint pattern are inlined here; the venue rows are imported and pinned by a hash
test (`tests/unit/taxonomy/test_reference_data.py`), so an edit of the data needs a new
migration. `events_app` gets the default privileges of `roles.sql` (no `DELETE` on
`venue`); `events_public` gets nothing on the new tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.modules.taxonomy.reference import reference_id
from app.modules.taxonomy.venue_reference import VENUES

revision: str = "0003_roles_taxonomy"
down_revision: str | None = "0002_events_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTROL_CHARS = r"[\x01-\x1f\x7f-\x9f\u2028\u2029]"
CATEGORY_SLUG_RENAMES = (
    ("lan-party", "lanparty"),
    ("fachschaft-fsi", "fachschaft-informatik-fsi"),
    ("fachschaft-tec", "fachschaft-technik-tec"),
    ("fachschaft-tex", "fachschaft-texoversum-tex"),
    ("fachschaft-ls", "fachschaft-life-sciences-ls"),
)

_GRANTS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
        REVOKE DELETE, TRUNCATE ON venue FROM events_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
        REVOKE ALL ON venue, membership FROM events_public;
    END IF;
END $$;
"""


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _create_venue() -> None:
    op.create_table(
        "venue",
        sa.Column("id", sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("postcode", sa.Text),
        sa.Column("city", sa.Text),
        sa.Column("building_no", sa.Text),
        sa.Column("room_key", sa.Text),
        sa.Column("campus_building_no", sa.Text),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lon", sa.Numeric(9, 6)),
        sa.Column("public_precision", sa.Text, server_default="hidden", nullable=False),
        sa.Column("is_private", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("geocode_source", sa.Text),
        sa.Column("geocoded_at", sa.DateTime(timezone=True)),
        sa.Column("legacy_wp_id", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_venue_slug"),
        sa.CheckConstraint(
            "public_precision IN ('exact', 'building', 'hidden')", name="ck_venue_public_precision"
        ),
        sa.CheckConstraint(
            "geocode_source IS NULL OR geocode_source IN ('pin', 'nominatim', 'import')",
            name="ck_venue_geocode_source",
        ),
        sa.CheckConstraint("(lat IS NULL) = (lon IS NULL)", name="ck_venue_coordinates_pair"),
        sa.CheckConstraint(
            "(lat IS NULL OR lat BETWEEN -90 AND 90) AND (lon IS NULL OR lon BETWEEN -180 AND 180)",
            name="ck_venue_coordinates_range",
        ),
        sa.CheckConstraint(f"name !~ '{CONTROL_CHARS}'", name="ck_venue_name_clean"),
        sa.CheckConstraint(f"address !~ '{CONTROL_CHARS}'", name="ck_venue_address_clean"),
        sa.CheckConstraint(f"notes !~ '{CONTROL_CHARS}'", name="ck_venue_notes_clean"),
    )


def _create_membership() -> None:
    op.create_table(
        "membership",
        sa.Column(
            "principal_id",
            sa.Uuid,
            sa.ForeignKey(
                "principal.id", ondelete="CASCADE", name="fk_membership_principal_id_principal"
            ),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey(
                "organization.id",
                ondelete="CASCADE",
                name="fk_membership_organization_id_organization",
            ),
            primary_key=True,
        ),
        sa.Column("role", sa.Text, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('viewer','submitter','organizer','approver')", name="ck_membership_role"
        ),
    )
    op.create_index("ix_membership_organization_id_role", "membership", ["organization_id", "role"])


def _apply_reference() -> None:
    for old, new in CATEGORY_SLUG_RENAMES:
        op.execute(
            sa.text("UPDATE category SET slug = :slug WHERE id = :id").bindparams(
                slug=new, id=reference_id("category", old)
            )
        )
    op.execute(
        sa.text("UPDATE organization SET legacy_wp_ids = '{}' WHERE id = :id").bindparams(
            id=reference_id("organization", "tec")
        )
    )
    venue = sa.table(
        "venue",
        *(
            sa.column(name)
            for name in (
                "id",
                "slug",
                "name",
                "address",
                "postcode",
                "city",
                "building_no",
                "room_key",
                "notes",
                "legacy_wp_id",
            )
        ),
    )
    op.bulk_insert(venue, [dict(row) for row in VENUES])


def upgrade() -> None:
    _create_venue()
    _create_membership()
    op.execute(_GRANTS)
    _apply_reference()


def downgrade() -> None:
    op.drop_table("membership")
    op.drop_table("venue")
    for old, _ in CATEGORY_SLUG_RENAMES:
        op.execute(
            sa.text("UPDATE category SET slug = :old WHERE id = :id").bindparams(
                old=old, id=reference_id("category", old)
            )
        )
    op.execute(
        sa.text("UPDATE organization SET legacy_wp_ids = '{174}' WHERE id = :id").bindparams(
            id=reference_id("organization", "tec")
        )
    )
