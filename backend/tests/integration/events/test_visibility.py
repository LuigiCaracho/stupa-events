"""PLAN 5.4, dossier level: who reads a dossier in each of its three states (404 otherwise)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def status_of(api: Api, user: str, event_id: str) -> int:
    return (await api.request(user, "GET", f"/api/events/{event_id}")).status_code


@pytest.mark.parametrize("state", ["draft", "published", "archived"])
async def test_the_dossier_rows_by_state(api: Api, state: str) -> None:
    eid = (await api.to_state(state))["id"]
    expected = {
        "organizer-fsi": 200,
        "viewer-fsi": 200,
        "editor": 200,
        "admin": 200,
        "stupa": 200,
        "organizer-makers": 404,
        "submitter-ekhg": 404,
        "member": 404,
    }
    assert {user: await status_of(api, user, eid) for user in expected} == expected
