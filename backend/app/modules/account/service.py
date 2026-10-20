"""Read and write the notification settings of the signed-in person."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.account.schemas import PrefIn, PrefOut, PrefsOut
from app.modules.notifications.kinds import KINDS, Kind, is_known, kind_of
from app.modules.notifications.models import NotificationPref
from app.shared.errors import FieldError, ValidationProblem


async def read_prefs(session: AsyncSession, sub: str) -> PrefsOut:
    """Return the switches for every kind; a missing row means everything on."""
    rows = await session.execute(
        select(NotificationPref).where(NotificationPref.principal_sub == sub)
    )
    stored = {p.kind: p for p in rows.scalars()}
    return PrefsOut(items=[_pref_out(k, stored.get(k.key)) for k in KINDS])


def _pref_out(kind: Kind, pref: NotificationPref | None) -> PrefOut:
    fixed = pref is None or kind.essential
    return PrefOut(
        kind=kind.key,
        in_app=True if pref is None or fixed else pref.in_app,
        mail=kind.mail and (True if pref is None or fixed else pref.mail),
        mail_available=kind.mail,
        essential=kind.essential,
    )


def validate_prefs(items: list[PrefIn]) -> None:
    """Reject unknown kinds and switching an essential kind off.

    Raises:
        ValidationProblem: 422 `unknown_kind` or `kind_essential`.
    """
    for item in items:
        if not is_known(item.kind):
            raise ValidationProblem(
                "Unknown notification kind.",
                code="unknown_kind",
                errors=[FieldError(field=item.kind, msg="unknown kind")],
            )
        if kind_of(item.kind).essential and not (item.in_app and item.mail):
            raise ValidationProblem(
                "This notification cannot be switched off.",
                code="kind_essential",
                errors=[FieldError(field=item.kind, msg="essential")],
            )


async def write_prefs(session: AsyncSession, sub: str, items: list[PrefIn]) -> None:
    """Upsert the given kinds (call `validate_prefs` first)."""
    for item in items:
        stmt = pg_insert(NotificationPref).values(
            principal_sub=sub, kind=item.kind, in_app=item.in_app, mail=item.mail
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["principal_sub", "kind"],
                set_={"in_app": item.in_app, "mail": item.mail, "updated_at": func.now()},
            )
        )
