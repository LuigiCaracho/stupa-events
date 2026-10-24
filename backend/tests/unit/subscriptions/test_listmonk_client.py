"""Listmonk HTTP client against a mocked transport: allowlist, requests and error texts."""

from __future__ import annotations

import json

import httpx
import pytest

from app.modules.subscriptions.listmonk_client import ListmonkClient, checked_base_url
from app.modules.subscriptions.listmonk_port import CampaignDraft, ListmonkError

BASE = "http://127.0.0.1:9002"


def client(handler) -> ListmonkClient:  # noqa: ANN001
    return ListmonkClient(BASE, "events-api", "t" * 32, transport=httpx.MockTransport(handler))


def ok(data: object) -> httpx.Response:
    return httpx.Response(200, json={"data": data})


def row(
    sid: int = 7,
    email: str = "a@example.test",
    lists: dict[int, str] | None = None,
    **extra: object,
) -> dict:
    return {
        "id": sid,
        "email": email,
        "status": "enabled",
        "attribs": {},
        "lists": [{"id": i, "subscription_status": s} for i, s in (lists or {}).items()],
        **extra,
    }


def test_production_needs_https() -> None:
    with pytest.raises(ListmonkError):
        checked_base_url(BASE, ["127.0.0.1"], development=False)
    assert checked_base_url("https://lm.example.test/", ["lm.example.test"], development=False) == (
        "https://lm.example.test"
    )


def test_development_allows_http_only_on_loopback() -> None:
    assert checked_base_url(BASE + "/", ["127.0.0.1"], development=True) == BASE
    with pytest.raises(ListmonkError):
        checked_base_url("http://lm.example.test", ["lm.example.test"], development=True)


def test_host_outside_the_allowlist_is_refused() -> None:
    with pytest.raises(ListmonkError) as raised:
        checked_base_url("https://evil.example.test", ["lm.example.test"], development=False)
    assert raised.value.kind == "host_not_allowed"
    with pytest.raises(ListmonkError):
        checked_base_url("https://lm.example.test", [], development=False)


async def test_lookup_uses_search_not_the_sql_query_and_matches_the_exact_address() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok({"results": [row(1, "xo'brien@example.test"), row(2, "O'Brien@example.test")]})

    found = await client(handler).find_subscriber("o'brien@example.test")
    assert found is not None and found.id == 2
    assert seen[0].headers["authorization"] == "token events-api:" + "t" * 32
    assert "query" not in seen[0].url.params
    assert seen[0].url.params["search"] == "o'brien@example.test"


async def test_control_characters_never_reach_the_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    for bad in ("a\n@example.test", "a\\b@example.test", "a\x00@example.test"):
        with pytest.raises(ListmonkError) as raised:
            await client(handler).find_subscriber(bad)
        assert not raised.value.retryable


async def test_redirect_is_not_followed_and_the_error_has_no_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"location": "http://169.254.169.254/"}, text="secret@example.test"
        )

    with pytest.raises(ListmonkError) as raised:
        await client(handler).find_subscriber("a@example.test")
    assert raised.value.status == 302
    assert "secret" not in str(raised.value)


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (503, True), (400, False), (404, False)]
)
async def test_status_decides_whether_a_retry_can_help(status: int, retryable: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="boom a@example.test")

    with pytest.raises(ListmonkError) as raised:
        await client(handler).delete_subscriber(3)
    assert raised.value.retryable is retryable
    assert "example.test" not in str(raised.value)


async def test_transport_error_is_retryable_and_names_only_the_class() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused a@example.test")

    with pytest.raises(ListmonkError) as raised:
        await client(handler).delete_subscriber(3)
    assert raised.value.retryable
    assert str(raised.value) == "ConnectError"


async def test_new_subscriber_is_created_preconfirmed_on_single_optin_lists() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return ok({"results": []})
        bodies.append(json.loads(request.content))
        return ok(row(lists={1: "confirmed", 2: "confirmed"}))

    result = await client(handler).upsert_subscriber(
        "a@example.test", {2, 1}, {"source": "get-started"}
    )
    assert bodies == [
        {
            "email": "a@example.test",
            "name": "STUPA Events Abo",
            "status": "enabled",
            "lists": [1, 2],
            "attribs": {"source": "get-started"},
            "preconfirm_subscriptions": True,
        }
    ]
    assert result.lists == {1: "confirmed", 2: "confirmed"}


async def test_existing_subscriber_uses_put_with_all_current_lists_and_removes_the_rest() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.method == "GET":
            return ok({"results": [row(lists={1: "confirmed", 2: "unsubscribed", 3: "confirmed"})]})
        return ok(True)

    await client(handler).upsert_subscriber("a@example.test", {1, 4}, {"profile_version": 2})
    methods = [(m, p) for m, p, _ in calls]
    assert ("PATCH", "/api/subscribers/7") not in methods
    put = next(b for m, p, b in calls if (m, p) == ("PUT", "/api/subscribers/7"))
    assert put["lists"] == [1, 2, 3, 4]
    assert put["attribs"] == {"profile_version": 2}
    remove = next(b for m, p, b in calls if (m, p) == ("PUT", "/api/subscribers/lists"))
    assert remove == {"ids": [7], "action": "remove", "target_list_ids": [3]}


async def test_unchanged_subscriber_makes_no_write() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return ok({"results": [row(lists={1: "confirmed"}, attribs={"a": 1})]})

    await client(handler).upsert_subscriber("a@example.test", {1}, {"a": 1})
    assert set(methods) == {"GET"}


async def test_blocklisted_subscriber_is_never_re_enabled() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return ok({"results": [{**row(), "status": "blocklisted"}]})

    result = await client(handler).upsert_subscriber("a@example.test", {1}, {})
    assert result.status == "blocklisted"
    assert set(methods) == {"GET"}


async def test_ensure_list_matches_the_exact_name_and_creates_a_private_single_optin_list() -> None:
    created: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return ok({"results": [{"id": 5, "name": "events-party-extra"}]})
        created.append(json.loads(request.content))
        return ok({"id": 9})

    assert await client(handler).ensure_list("party", "events-party") == 9
    assert created == [
        {"name": "events-party", "type": "private", "optin": "single", "tags": ["events"]}
    ]


async def test_campaign_has_no_send_time_and_lookup_is_exact() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return ok({"results": [{"id": 1, "name": "events-digest-2026-10-26-party-x"}]})
        bodies.append(json.loads(request.content))
        return ok({"id": 4})

    lm = client(handler)
    assert await lm.find_campaign("events-digest-2026-10-26-party") is None
    assert await lm.create_campaign(CampaignDraft("n", "s", (3,), "<p>x</p>")) == 4
    assert "send_at" not in bodies[0]
    assert bodies[0]["lists"] == [3]


async def test_list_states_pages_and_deduplicates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        count = 500 if page == 1 else 3
        return ok(
            {
                "results": [
                    row(sid=page * 1000 + i, email=f"u{page}-{i}@example.test")
                    for i in range(count)
                ]
            }
        )

    seen = [s async for s in client(handler).list_states({4})]
    assert len(seen) == 503


async def test_subscriber_count_asks_for_confirmed_subscriptions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["subscription_status"] == "confirmed"
        return ok({"total": 12, "results": []})

    assert await client(handler).subscriber_count(4) == 12
