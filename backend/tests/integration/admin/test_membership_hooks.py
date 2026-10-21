"""The sync hooks against a real database: login, revalidation, mappings, trust, deactivation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.modules.admin.membership_sync import sync_principal_memberships
from app.modules.auth import oidc, service, session_renewal
from app.modules.auth.models import AuthSession
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.oidc import OidcClaims
from app.modules.auth.session_renewal import renew_principal_session
from app.settings import load_settings
from tests._support.factories import make_settings
from tests.integration.events.harness import Api as ApiHandle

pytestmark = pytest.mark.integration
MAPPINGS = "/api/admin/group-mappings"


async def held(api: ApiHandle, sub: str) -> set[tuple[str, str]]:
    async with api.maker() as db:
        rows = await db.execute(
            text(
                "SELECT o.slug, m.role FROM membership m JOIN organization o ON o.id = m.organization_id "
                "JOIN principal p ON p.id = m.principal_id WHERE p.sub = :s"
            ),
            {"s": sub},
        )
        return {(r.slug, r.role) for r in rows}


async def add_person(api: ApiHandle, sub: str, groups: list[str]) -> None:
    async with api.maker() as db:
        db.add(PrincipalRow(sub=sub, oidc_groups=groups))
        await db.commit()


async def map_group(
    api: ApiHandle, group: str, role: str, org: str | None = None
) -> dict[str, Any]:
    body = {"oidcGroup": group, "role": role, "organizationId": api.org_ids[org] if org else None}
    response = await api.request("admin", "POST", MAPPINGS, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_new_mapping_creates_the_membership_and_deleting_it_removes_it(
    api: ApiHandle,
) -> None:
    await add_person(api, "p1", ["Campus-FSI"])
    mapping = await map_group(api, "Campus-FSI", "organizer", "fsi")
    assert await held(api, "p1") == {("fsi", "organizer")}
    changed = await api.request(
        "admin", "PATCH", f"{MAPPINGS}/{mapping['id']}", json={"role": "viewer"}
    )
    assert changed.status_code == 200
    assert await held(api, "p1") == {("fsi", "viewer")}
    await api.request("admin", "DELETE", f"{MAPPINGS}/{mapping['id']}")
    assert await held(api, "p1") == set()


async def test_the_login_callback_writes_the_membership(
    api: ApiHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    await map_group(api, "Login-Gruppe", "submitter", "ekhg")
    claims = OidcClaims(sub="p3", email="p3@example.org", name="P3", groups=["Login-Gruppe"])

    async def exchange(_s: Any, **_k: Any) -> dict[str, str]:
        return {"id_token": "idt", "refresh_token": "rt"}

    async def verify(_s: Any, **_k: Any) -> OidcClaims:
        return claims

    monkeypatch.setattr(oidc, "exchange_code", exchange)
    monkeypatch.setattr(oidc, "verify_id_token", verify)
    async with api.maker() as db:
        await service.oidc_callback(db, make_settings(), code="c", verifier="v", nonce="n")
        await db.commit()
    assert await held(api, "p3") == {("ekhg", "submitter")}
    async with api.maker() as db:
        entries = (
            await db.execute(
                text("SELECT actor, data FROM audit_entry WHERE action = 'role_change'")
            )
        ).all()
    assert [(e.actor, e.data["role"], e.data["change"]) for e in entries] == [
        ("oidc-sync", "submitter", "added")
    ]
    assert "p3@example.org" not in str(entries)


async def seed_session(api: ApiHandle, sub: str, group: str) -> Any:
    """Create a person in `fsi` with a session whose revalidation is due; return the row id."""
    await map_group(api, group, "organizer", "fsi")
    await add_person(api, sub, [group])
    async with api.maker() as db:
        person = (
            await db.execute(text("SELECT id FROM principal WHERE sub = :s"), {"s": sub})
        ).scalar_one()
        now = datetime.now(UTC)
        db.add(
            AuthSession(
                sid=f"s-{sub}",
                principal_id=person,
                expires_at=now + timedelta(days=1),
                refresh_token="rt",
                id_token="old",
                revalidated_at=now - timedelta(hours=5),
            )
        )
        await sync_principal_memberships(db, await db.get(PrincipalRow, person))
        await db.commit()
    return person


async def renew(api: ApiHandle, sub: str, person: Any) -> bool:
    settings = load_settings(
        database_url="postgresql+asyncpg://x/y",
        session_secret="session-secret-0123",
        oidc_issuer="https://sso.example/",
        oidc_client_id="events",
        oidc_client_secret="client-secret-01234",
        oidc_redirect_url="https://events.example/api/auth/callback",
    )
    async with api.maker() as db:
        session = (
            await db.execute(text("SELECT id FROM auth_session WHERE sid = :s"), {"s": f"s-{sub}"})
        ).scalar_one()
        return await renew_principal_session(
            db,
            settings,
            session=await db.get(AuthSession, session),
            principal=await db.get(PrincipalRow, person),
            now=datetime.now(UTC),
        )


async def session_count(api: ApiHandle, sub: str) -> int:
    async with api.maker() as db:
        return (
            await db.execute(
                text("SELECT count(*) FROM auth_session WHERE sid = :s"), {"s": f"s-{sub}"}
            )
        ).scalar_one()


async def test_the_revalidation_removes_a_withdrawn_group(
    api: ApiHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    person = await seed_session(api, "p4", "Reval-Gruppe")
    assert await held(api, "p4") == {("fsi", "organizer")}

    async def refresh(_s: Any, *, refresh_token: str) -> dict[str, str]:
        return {"id_token": "new"}

    async def refreshed(_s: Any, *, id_token: str, cached: OidcClaims) -> OidcClaims:
        return OidcClaims(sub="p4", email=None, name=None, groups=[])

    monkeypatch.setattr(oidc, "refresh_tokens", refresh)
    monkeypatch.setattr(oidc, "verify_refreshed_id_token", refreshed)
    assert await renew(api, "p4", person)
    assert await held(api, "p4") == set()


async def test_an_idp_outage_within_the_grace_time_keeps_memberships_and_session(
    api: ApiHandle, monkeypatch: pytest.MonkeyPatch
) -> None:
    person = await seed_session(api, "p8", "Outage-Gruppe")

    async def down(_s: Any, *, refresh_token: str) -> dict[str, str]:
        raise oidc.OidcUnavailableError("idp down")

    monkeypatch.setattr(oidc, "refresh_tokens", down)
    monkeypatch.setattr(session_renewal, "_idp_retry_after", 0.0)
    assert await renew(api, "p8", person)
    assert await held(api, "p8") == {("fsi", "organizer")}
    assert await session_count(api, "p8") == 1


async def test_deactivating_an_organization_drops_its_memberships(api: ApiHandle) -> None:
    await add_person(api, "p9", ["Inaktiv-Gruppe"])
    await map_group(api, "Inaktiv-Gruppe", "organizer", "makers")
    assert await held(api, "p9") == {("makers", "organizer")}
    org = f"/api/admin/organizations/{api.org_ids['makers']}"
    assert (await api.request("admin", "PATCH", org, json={"active": False})).status_code == 200
    assert await held(api, "p9") == set()
    assert (await api.request("admin", "PATCH", org, json={"active": True})).status_code == 200
    assert await held(api, "p9") == {("makers", "organizer")}


async def test_a_deactivated_person_and_a_system_group_hold_nothing(api: ApiHandle) -> None:
    await map_group(api, "Normal", "viewer", "fsi")
    await add_person(api, "p5", ["Normal", "events-system:Normal"])
    await map_group(api, "Anderes", "viewer", "makers")
    assert await held(api, "p5") == {("fsi", "viewer")}
    async with api.maker() as db:
        row = (await db.execute(text("SELECT id FROM principal WHERE sub = 'p5'"))).scalar_one()
        person = await db.get(PrincipalRow, row)
        assert person is not None
        person.active = False
        assert await sync_principal_memberships(db, person) is True
        await db.commit()
    assert await held(api, "p5") == set()


async def test_the_principal_list_filters_by_organization_through_the_membership(
    api: ApiHandle,
) -> None:
    await add_person(api, "p6", ["Liste-Gruppe"])
    await add_person(api, "p7", [])
    await map_group(api, "Liste-Gruppe", "viewer", "fsi")
    url = f"/api/admin/principals?organizationId={api.org_ids['fsi']}"
    listed = (await api.request("admin", "GET", url)).json()
    assert [p["sub"] for p in listed["items"]] == ["p6"]
