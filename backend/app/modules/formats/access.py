"""Who may change a format and its master howto: editors and organizers of its organization."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.formats.models import Format
from app.modules.orgs.scope import bind
from app.shared.errors import ForbiddenError


async def ensure_can_manage(session: AsyncSession, principal: Principal, fmt: Format) -> None:
    """Require `format.manage`, or `event.publish` in the organization of the format (403).

    The format itself is readable for everybody with `library.read`; only changes need this.
    """
    await bind(session, principal)
    if principal.has("format.manage") or principal.has("event.publish", fmt.organization_id):
        return
    raise ForbiddenError("Missing permission: format.manage")
