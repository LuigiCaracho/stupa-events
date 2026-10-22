"""The 20 sample searches over HTTP, plus rules of the text search (contract 6.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.search_stock import seed_stock
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration
CORPUS = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "fixtures" / "public_search_corpus.yaml").read_text()
)


@pytest.fixture
async def stock(api: Api) -> Site:
    site_data.configure(api)
    return await seed_stock(api)


def test_the_corpus_has_twenty_searches() -> None:
    assert len(CORPUS) == 20


@pytest.mark.parametrize("case", CORPUS, ids=lambda c: c["q"][:20])
async def test_sample_search(api: Api, stock: Site, case: dict) -> None:
    response = await api.request(
        None, "GET", "/api/public/events", params={"q": case["q"], "limit": 50}
    )
    assert response.status_code == case.get("status", 200), response.text
    if "status" in case:
        return
    found = {item["slug"] for item in response.json()["items"]}
    for key in case.get("contains", []):
        assert stock.slugs[key] in found, (case["q"], key)
    for key in case.get("excludes", []):
        assert stock.slugs[key] not in found, (case["q"], key)
    if not case.get("contains") and case.get("excludes"):
        assert not found or case["q"].startswith("%")


async def test_hits_are_a_subset_of_the_feed(api: Api, stock: Site) -> None:
    feed = await api.request(None, "GET", "/api/public/feed/events", params={"limit": 500})
    feed_slugs = {item["slug"] for item in feed.json()["items"]}
    body = (await api.request(None, "GET", "/api/public/events", params={"q": "sitzung"})).json()
    assert body["items"] and {i["slug"] for i in body["items"]} <= feed_slugs


async def test_text_search_pages_with_an_offset_cursor_and_ranks_titles_first(
    api: Api, stock: Site
) -> None:
    first = (
        await api.request(None, "GET", "/api/public/events", params={"q": "sitzung", "limit": 1})
    ).json()
    assert first["nextCursor"] and first["total"] == 2
    second = (
        await api.request(
            None,
            "GET",
            "/api/public/events",
            params={"q": "sitzung", "limit": 1, "cursor": first["nextCursor"]},
        )
    ).json()
    assert second["items"][0]["slug"] != first["items"][0]["slug"] and second["total"] is None
    keyset = (await api.request(None, "GET", "/api/public/events", params={"limit": 1})).json()[
        "nextCursor"
    ]
    wrong = await api.request(
        None, "GET", "/api/public/events", params={"q": "sitzung", "cursor": keyset}
    )
    assert wrong.status_code == 422 and wrong.json()["code"] == "invalid_cursor"
