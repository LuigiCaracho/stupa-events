"""Principal helpers, session helpers and bootstrap branches that M1 left uncovered."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.modules.auth import bootstrap, sessions
from app.modules.auth.principal import Principal
from tests._support.auth_fakes import fake_session, result
from tests._support.factories import make_settings


def test_has_in_org_and_scope_helpers() -> None:
    principal = Principal(
        sub="s",
        roles=["member"],
        permissions={"library.read"},
        org_roles={"fsi": frozenset({"organizer"})},
    )
    assert principal.has_in_org("event.publish", "fsi") is True
    assert principal.has_in_org("event.publish", "makers") is False
    assert principal.has_in_org("library.read", "makers") is True
    capped = Principal(sub="s", roles=["admin"], scope_permissions=frozenset({"library.read"}))
    assert capped.has_in_org("event.edit", "fsi") is False
    assert capped.is_admin is True and capped.scope_allows("library.read") is True
    assert capped.scope_allows("event.edit") is False
    assert principal.scope_allows("anything") is True
    assert principal.in_group("g") is False


async def test_end_other_sessions_keeps_or_drops_the_named_one() -> None:
    class Db:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def execute(self, statement: object) -> SimpleNamespace:
            self.statements.append(str(statement))
            return SimpleNamespace(rowcount=2)

    db = Db()
    assert await sessions.end_other_principal_sessions(db, uuid4(), "keep") == 2  # type: ignore[arg-type]
    assert await sessions.end_other_principal_sessions(db, uuid4(), None) == 2  # type: ignore[arg-type]
    assert "sid !=" in db.statements[0] and "sid !=" not in db.statements[1]


async def test_end_principal_sessions_reports_the_count() -> None:
    class Db:
        async def execute(self, _s: object) -> SimpleNamespace:
            return SimpleNamespace(rowcount=None)

    assert await sessions.end_principal_sessions(Db(), uuid4()) == 0  # type: ignore[arg-type]


def test_a_transaction_cookie_without_return_to_loads_without_it() -> None:
    cookie = sessions.issue_oidc_tx("secret", "st", "ver", "non", "web", None)
    tx = sessions.load_oidc_tx("secret", cookie, 600)
    assert tx is not None and "return_to" not in tx
    assert sessions.load_oidc_tx("secret", "garbage", 600) is None


async def test_the_session_helpers_return_none_for_a_missing_row() -> None:
    cookie = sessions.sign_principal_sid("secret", "sid-1")
    db = fake_session(result())
    assert (
        await sessions.delete_principal_session(
            db, secret="secret", cookie_value=cookie, max_age=sessions.SESSION_COOKIE_MAX_AGE
        )
        is None
    )
    assert (
        await sessions.delete_principal_session(
            db, secret="secret", cookie_value="forged", max_age=sessions.SESSION_COOKIE_MAX_AGE
        )
        is None
    )


async def test_the_bootstrap_sweep_with_nothing_to_flag_flushes_nothing() -> None:
    db = fake_session(result())
    settings = make_settings(bootstrap_admin_subjects="root")
    assert await bootstrap.ensure_bootstrap_admins(db, settings) == 0
    assert db.flushed == 0
