"""The 20 sample searches of the M5 contract run against a real database (`queries.yaml`)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.events.harness import Api
from tests.integration.search.corpus import load_corpus, load_yaml

pytestmark = pytest.mark.integration
QUERIES = load_yaml("queries.yaml")


async def ask(api: Api, user: str, q: str, **params: Any) -> dict:
    response = await api.request(user, "GET", "/api/search", params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("case", QUERIES, ids=lambda c: f"{c['n']:02d}-{c['q'][:20]}")
async def test_search_20(api: Api, case: dict[str, Any]) -> None:
    await load_corpus(api)
    params = {"scope": case.get("scope", "events"), **case.get("params", {})}
    found = await ask(api, case["as"], case["q"], limit=50, **params)
    titles = [hit["title"] for hit in found["hits"]]
    assert sorted(titles) == sorted(case["expect"]), found
    assert found["total"] == len(case["expect"])
    if "first" in case:
        assert titles[0] == case["first"]
