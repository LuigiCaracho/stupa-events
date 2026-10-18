"""Organizations and group mappings: the `organization` and `group_mapping` tables.

An organization is the organizer and the scope of a right (PLAN 3.3, 5). `trusted` lets
an `approver` of the organization approve. `group_mapping` adds a grant that the group
name does not express; `app.modules.auth.rbac` reads it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Integer

from app.db import Base, TimestampMixin, UUIDPkMixin
from app.shared.permissions import GLOBAL_ROLES, ORG_ROLES

ORGANIZATION_KINDS = ("stupa", "referat", "fachschaft", "partner", "hochschule", "redaktion")


class Organization(UUIDPkMixin, TimestampMixin, Base):
    """An organizer and the scope of organization roles."""

    __tablename__ = "organization"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="RESTRICT"), nullable=True
    )
    short: Mapped[str] = mapped_column(Text)
    color_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    contact_public: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trusted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    instagram: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    legacy_wp_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        CheckConstraint(
            "kind IN (" + ", ".join(repr(k) for k in ORGANIZATION_KINDS) + ")", name="kind"
        ),
    )


class GroupMapping(UUIDPkMixin, TimestampMixin, Base):
    """Maps an OIDC group to a role, globally or in one organization."""

    __tablename__ = "group_mapping"

    oidc_group: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[str] = mapped_column(Text)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("organization.id", ondelete="CASCADE"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "role IN (" + ", ".join(repr(r) for r in (*GLOBAL_ROLES, *ORG_ROLES)) + ")",
            name="role",
        ),
        CheckConstraint(
            "(organization_id IS NULL) = (role IN ("
            + ", ".join(repr(r) for r in GLOBAL_ROLES)
            + "))",
            name="scope",
        ),
        CheckConstraint("oidc_group NOT LIKE 'events-system:%'", name="reserved_namespace"),
    )
