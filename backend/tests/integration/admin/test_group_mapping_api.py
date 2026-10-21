"""The group mapping API: validation codes, duplicates, last-admin protection, defaults, audit."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration
URL = "/api/admin/group-mappings"


async def post(api: Api, **body: object):
    return await api.request("admin", "POST", URL, json=body)


async def test_create_list_update_delete(api: Api) -> None:
    made = await post(
        api, oidcGroup="Campus-FSI", role="organizer", organizationId=api.org_ids["fsi"]
    )
    assert made.status_code == 201
    row = made.json()
    assert row["oidcGroup"] == "Campus-FSI" and row["role"] == "organizer"
    assert row["organization"]["slug"] == "fsi" and row["principalCount"] == 0
    listed = (await api.request("admin", "GET", URL)).json()
    assert row["id"] in [m["id"] for m in listed]
    assert [m["oidcGroup"] for m in listed] == sorted(m["oidcGroup"] for m in listed)
    patched = await api.request("admin", "PATCH", f"{URL}/{row['id']}", json={"role": "viewer"})
    assert patched.status_code == 200 and patched.json()["role"] == "viewer"
    assert (await api.request("admin", "DELETE", f"{URL}/{row['id']}")).status_code == 204
    assert (await api.request("admin", "DELETE", f"{URL}/{row['id']}")).status_code == 404


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        ({"oidcGroup": "events-system:x", "role": "admin"}, "reserved_group_prefix", "oidcGroup"),
        ({"oidcGroup": "g", "role": "organizer"}, "organization_required", "organizationId"),
        (
            {"oidcGroup": "g", "role": "editor", "organizationId": "fsi"},
            "organization_forbidden",
            "organizationId",
        ),
        ({"oidcGroup": "g", "role": "member"}, "implicit_role", "role"),
        (
            {
                "oidcGroup": "g",
                "role": "viewer",
                "organizationId": "00000000-0000-0000-0000-000000000000",
            },
            "unknown_organization",
            "organizationId",
        ),
    ],
)
async def test_every_validation_code(api: Api, body: dict, code: str, field: str) -> None:
    if body.get("organizationId") == "fsi":
        body = {**body, "organizationId": api.org_ids["fsi"]}
    response = await post(api, **body)
    problem = response.json()
    assert response.status_code == 422 and problem["code"] == code
    assert field in [e["field"] for e in problem["errors"]]
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_the_retired_approver_role_is_refused(api: Api) -> None:
    refused = await post(
        api, oidcGroup="Freigabe", role="approver", organizationId=api.org_ids["fsi"]
    )
    assert refused.status_code == 422


async def test_unknown_role_and_unknown_fields_are_validation_errors(api: Api) -> None:
    assert (await post(api, oidcGroup="g", role="root")).status_code == 422
    assert (await post(api, oidcGroup="g", role="editor", extra=1)).status_code == 422
    assert (await post(api, oidcGroup="", role="editor")).status_code == 422


async def test_a_group_can_be_mapped_once(api: Api) -> None:
    assert (await post(api, oidcGroup="Doppelt", role="editor")).status_code == 201
    again = await post(api, oidcGroup="Doppelt", role="stupa")
    assert again.status_code == 409 and again.json()["code"] == "duplicate_group"


async def test_the_group_name_cannot_change(api: Api) -> None:
    row = (await post(api, oidcGroup="Alt", role="editor")).json()
    response = await api.request("admin", "PATCH", f"{URL}/{row['id']}", json={"oidcGroup": "Neu"})
    assert response.status_code == 422


async def test_patch_validates_the_merged_pair(api: Api) -> None:
    row = (await post(api, oidcGroup="Wechsel", role="editor")).json()
    to_org_role = await api.request("admin", "PATCH", f"{URL}/{row['id']}", json={"role": "viewer"})
    assert to_org_role.json()["code"] == "organization_required"
    ok = await api.request(
        "admin",
        "PATCH",
        f"{URL}/{row['id']}",
        json={"role": "viewer", "organizationId": api.org_ids["fsi"]},
    )
    assert ok.status_code == 200
    back = await api.request(
        "admin", "PATCH", f"{URL}/{row['id']}", json={"role": "editor", "organizationId": None}
    )
    assert back.status_code == 200 and back.json()["organization"] is None
    assert (await api.request("admin", "PATCH", f"{URL}/{row['id']}", json={})).status_code == 200


async def test_the_last_admin_mapping_stays_without_bootstrap_admins(api: Api) -> None:
    admins = [m for m in (await api.request("admin", "GET", URL)).json() if m["role"] == "admin"]
    assert len(admins) == 1
    gone = await api.request("admin", "DELETE", f"{URL}/{admins[0]['id']}")
    assert gone.status_code == 409 and gone.json()["code"] == "last_admin_mapping"
    demote = await api.request(
        "admin", "PATCH", f"{URL}/{admins[0]['id']}", json={"role": "editor"}
    )
    assert demote.status_code == 409
    await post(api, oidcGroup="Zweiter-Admin", role="admin")
    assert (await api.request("admin", "DELETE", f"{URL}/{admins[0]['id']}")).status_code == 204


async def test_a_bootstrap_admin_list_lifts_the_protection(api: Api) -> None:
    from app.settings import get_settings
    from tests._support.factories import make_settings

    app = api.client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: make_settings(bootstrap_admin_subjects="root")
    admins = [m for m in (await api.request("admin", "GET", URL)).json() if m["role"] == "admin"]
    assert (await api.request("admin", "DELETE", f"{URL}/{admins[0]['id']}")).status_code == 204


async def test_defaults_are_idempotent(api: Api) -> None:
    first = (await api.request("admin", "POST", f"{URL}/defaults", json={})).json()
    groups = {m["oidcGroup"] for m in first}
    assert {"events-care-viewer", "events-care-submitter", "events-care-organizer"} <= groups
    assert not {g for g in groups if g.endswith("-approver")}
    assert not groups & {"events-admin", "events-fsi-viewer"}  # the harness mapped these already
    assert (await api.request("admin", "POST", f"{URL}/defaults", json={})).json() == []


async def test_mutations_write_audit_entries_without_personal_data(api: Api) -> None:
    row = (await post(api, oidcGroup="Audit-Gruppe", role="editor")).json()
    await api.request("admin", "DELETE", f"{URL}/{row['id']}")
    async with api.maker() as session:
        entries = (
            await session.execute(
                text(
                    "SELECT action, target_type, data FROM audit_entry "
                    "WHERE action = 'role_mapping_change' ORDER BY id"
                )
            )
        ).all()
    assert [e.data["change"] for e in entries] == ["created", "deleted"]
    assert entries[0].target_type == "group_mapping"
    assert entries[0].data["oidcGroup"] == "Audit-Gruppe"
    assert "@" not in str(entries)


async def test_principal_count_counts_cached_groups(api: Api) -> None:
    async with api.maker() as session:
        await session.execute(
            text(
                "INSERT INTO principal (sub, oidc_groups) VALUES "
                "('c1', '[\"Zaehl-Gruppe\", \"x\"]'), ('c2', '[\"Zaehl-Gruppe\"]'), ('c3', '[\"y\"]')"
            )
        )
        await session.commit()
    row = (await post(api, oidcGroup="Zaehl-Gruppe", role="editor")).json()
    assert row["principalCount"] == 2


async def test_a_blank_group_is_422(api: Api) -> None:
    assert (await post(api, oidcGroup="   ", role="admin")).status_code == 422
