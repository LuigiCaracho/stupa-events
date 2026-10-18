"""Identity and session tables: `principal` and `auth_session` (definitions only).

Roles are code (`app.shared.permissions`), not rows. An OIDC group grants them, and the
optional `group_mapping` table (migration `0002_events_core`) adds grants that a group
name does not express.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/models.py (roles tables removed)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, CreatedAtMixin, UUIDPkMixin

SESSION_CLIENT_WEB = "web"
SESSION_CLIENT_PWA = "pwa"
SESSION_CLIENTS = (SESSION_CLIENT_WEB, SESSION_CLIENT_PWA)
DEFAULT_WEB_SESSION_DAYS = 90
DEFAULT_PWA_SESSION_DAYS = 180
MAX_SESSION_DAYS = 400


def session_days(client: str) -> int:
    """Return the lifetime in days of a session of `client` (`web` or `pwa`)."""
    return DEFAULT_PWA_SESSION_DAYS if client == SESSION_CLIENT_PWA else DEFAULT_WEB_SESSION_DAYS


class Principal(UUIDPkMixin, Base):
    """OIDC subject from the IdP.

    The PII, the email address, stays in this table. It never enters the audit `data`
    column.
    """

    __tablename__ = "principal"

    sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    oidc_groups: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    # Set at login when the `sub` or the verified email matches the bootstrap lists. The
    # resolver grants the `admin` role only while the lists still name the principal.
    bootstrap_admin: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)


class AuthSession(UUIDPkMixin, CreatedAtMixin, Base):
    """Server session of an OIDC principal.

    The browser gets only a signed, opaque `sid` in an HttpOnly cookie. No JWT reaches
    JavaScript. The id token and the refresh token stay on the server for the refresh
    and the logout.
    """

    __tablename__ = "auth_session"

    sid: Mapped[str] = mapped_column(Text, unique=True)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principal.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    client: Mapped[str] = mapped_column(
        Text, server_default=SESSION_CLIENT_WEB, default=SESSION_CLIENT_WEB
    )
    revalidated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_auth_session_principal_id", "principal_id"),
        CheckConstraint("client IN ('web', 'pwa')", name="client"),
    )
