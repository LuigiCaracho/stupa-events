"""The search API beyond the 20 samples: paging, rights, highlights, scopes, errors."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from app.modules.search import query, service
from tests.integration.events.harness import Api
from tests.integration.search.corpus import load_corpus

pytestmark = pytest.mark.integration


async def ask(api: Api, user: str | None, **params: Any) -> Any:
    return await api.request(user, "GET", "/api/search", params=params)


async def test_search_needs_a_login(api: Api) -> None:
    assert (await ask(api, None, q="movienight")).status_code == 401


async def test_total_equals_the_length_of_the_walked_hits(api: Api) -> None:
    await load_corpus(api)
    seen: list[str] = []
    total = -1
    for offset in range(0, 12, 2):
        page = (await ask(api, "editor", q="movienight", limit=2, offset=offset)).json()
        total = page["total"]
        seen += [hit["id"] for hit in page["hits"]]
    assert total == len(seen) == len(set(seen)) == 5


async def test_hits_and_facets_never_count_rows_the_reader_may_not_see(api: Api) -> None:
    await load_corpus(api)
    own = (await ask(api, "organizer-fsi", q="movienight")).json()
    foreign = (await ask(api, "organizer-makers", q="movienight")).json()
    assert own["total"] == 5 and foreign["total"] == 3
    states = {f["value"]: f["count"] for f in foreign["facets"]["state"]}
    assert states == {"archived": 3}
    assert all(hit["foreign"] for hit in foreign["hits"])
    nobody = (await ask(api, "member", q="Sitzung")).json()
    assert [hit["title"] for hit in nobody["hits"]] == ["STUPA-Sitzung"]


async def test_a_team_document_is_found_by_its_team_only(api: Api) -> None:
    await load_corpus(api)
    for user, want in (("organizer-fsi", 1), ("organizer-makers", 0), ("member", 0)):
        found = (await ask(api, user, q="Kontext-Notiz", scope="documents")).json()
        assert found["total"] == want, user
    fsi = (await ask(api, "organizer-fsi", q="Kontext-Notiz", scope="documents")).json()
    assert fsi["hits"][0]["link"].endswith("/anleitung") and fsi["hits"][0]["link"].startswith(
        "/dossiers/"
    )


async def test_hits_carry_highlight_segments_and_never_html(api: Api) -> None:
    await load_corpus(api)
    await api.sql(
        "UPDATE event SET title = 'Whiplash <b>live</b>' WHERE title = 'Movienight: Whiplash'"
    )
    found = (await ask(api, "organizer-fsi", q="whiplash")).json()
    highlight = found["hits"][0]["highlights"][0]
    assert highlight["field"] == "title"
    assert any(s["hit"] and s["text"].lower() == "whiplash" for s in highlight["segments"])
    # The whole title comes back as plain text (HighlightAll); markup in it stays text, the
    # client renders segments with text nodes only.
    assert "".join(s["text"] for s in highlight["segments"]) == "Whiplash <b>live</b>"
    assert [s["text"] for s in highlight["segments"] if s["hit"]] == ["Whiplash"]
    assert "\x01" not in str(found) and "\x02" not in str(found)


async def test_the_title_highlight_keeps_the_whole_title(api: Api) -> None:
    await load_corpus(api)
    found = (await ask(api, "organizer-fsi", q="Arrival")).json()
    hit = next(h for h in found["hits"] if h["title"] == "STUPA Movienight: Arrival (OmU)")
    title = next(h for h in hit["highlights"] if h["field"] == "title")
    assert "".join(s["text"] for s in title["segments"]) == hit["title"]
    assert [s["text"] for s in title["segments"] if s["hit"]] == ["Arrival"]


async def test_a_typo_without_hits_gets_a_suggestion(api: Api) -> None:
    await load_corpus(api)
    found = (await ask(api, "organizer-fsi", q="Kinabnd")).json()
    assert found["total"] == 0 and found["suggestion"] == "Kinoabend"
    assert (await ask(api, "organizer-fsi", q="Kinoabend")).json()["suggestion"] is None
    assert (await ask(api, "organizer-fsi", q="Zzzz")).json()["suggestion"] is None


async def test_scopes_documents_and_formats(api: Api) -> None:
    await load_corpus(api)
    formats = (await ask(api, "member", q="movienight", scope="formats")).json()
    assert [(h["kind"], h["title"]) for h in formats["hits"]] == [
        ("format", "Movienight"),
        ("format", "Caipi Night"),
    ]
    assert formats["hits"][0]["link"] == "/formate/movienight"
    documents = (await ask(api, "organizer-fsi", q="popcornmaschine", scope="documents")).json()
    assert documents["hits"][0]["kind"] == "document"
    assert documents["hits"][0]["subtitle"].startswith("Filmquiz")


async def test_facets_list_organization_year_category_and_format(api: Api) -> None:
    await load_corpus(api)
    found = (await ask(api, "organizer-fsi", q="movienight")).json()["facets"]
    assert {f["value"] for f in found["organization"]} == {"fsi"}
    assert {f["value"] for f in found["year"]} == {"2025", "2026"}
    assert {f["value"]: f["count"] for f in found["format"]} == {"movienight": 5}


@pytest.mark.parametrize(
    ("q", "status", "code"),
    [("x" * 101, 422, "query_too_long"), ("a\x00b", 422, "invalid_query"), ("x", 200, None)],
)
async def test_input_limits(api: Api, q: str, status: int, code: str | None) -> None:
    response = await ask(api, "editor", q=q)
    assert response.status_code == status
    if code:
        assert response.json()["code"] == code


async def test_a_slow_statement_is_a_503_search_timeout(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    await load_corpus(api)
    real = query.build

    def slow(*args: Any, **kwargs: Any) -> query.Statements:
        built = real(*args, **kwargs)
        return query.Statements(
            total=text("SELECT pg_sleep(2)"),
            facets=built.facets,
            page=built.page,
            headline_sql=built.headline_sql,
            params=built.params,
        )

    monkeypatch.setattr(service.query, "build", slow)
    monkeypatch.setattr(service, "STATEMENT_TIMEOUT", "100ms")
    response = await ask(api, "editor", q="movienight")
    assert response.status_code == 503 and response.json()["code"] == "search_timeout"


async def test_percent_and_underscore_are_no_wildcards(api: Api) -> None:
    await load_corpus(api)
    for q in ("%%", "__", "\\"):
        assert (await ask(api, "organizer-fsi", q=q)).json()["total"] == 0


async def test_other_database_errors_are_not_mistaken_for_a_timeout(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    await load_corpus(api)
    real = query.build

    def broken(*args: Any, **kwargs: Any) -> query.Statements:
        built = real(*args, **kwargs)
        return query.Statements(
            total=text("SELEC 1"),
            facets=built.facets,
            page=built.page,
            headline_sql=built.headline_sql,
            params=built.params,
        )

    monkeypatch.setattr(service.query, "build", broken)
    with pytest.raises(Exception, match="syntax"):
        await ask(api, "editor", q="movienight")
