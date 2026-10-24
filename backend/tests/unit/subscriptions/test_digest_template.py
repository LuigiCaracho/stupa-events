"""Digest body: Go-template injection, HTML escaping and the footer placeholder."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.modules.subscriptions.digest_template import DigestEvent, render_digest, when

START = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)


def event(title: str = "Halloween-Party", **extra: object) -> DigestEvent:
    fields = {
        "slug": "halloween",
        "starts_at": START,
        "all_day": False,
        "venue": "Mensa",
        "category": "Party",
    }
    return DigestEvent(title=title, **{**fields, **extra})  # type: ignore[arg-type]


def render(*events: DigestEvent) -> str:
    return render_digest(
        list(events), base_url="https://events.example.test/", week_start=date(2026, 10, 26)
    )


def test_go_template_in_a_title_stays_text() -> None:
    html = render(event("{{ .Subscriber.Email }}"))
    assert "{{ .Subscriber" not in html
    assert "&#123;&#123; .Subscriber.Email &#125;&#125;" in html


def test_html_in_a_title_is_escaped() -> None:
    html = render(event("<script>alert(1)</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_only_the_footer_keeps_a_real_placeholder() -> None:
    html = render(event("{{ .Subscriber.Email }}", venue="{{ x }}"))
    assert html.count("{{") == 1
    assert "{{ UnsubscribeURL }}" in html


def test_event_link_and_berlin_time() -> None:
    html = render(event())
    assert 'href="https://events.example.test/e/halloween"' in html
    assert "Fr., 30.10., 18:00 Uhr" in html


def test_all_day_event_has_no_clock_time() -> None:
    assert when(START, True) == "Fr., 30.10."


def test_summer_time_is_applied() -> None:
    assert when(datetime(2026, 7, 1, 17, 0, tzinfo=UTC), False) == "Mi., 01.07., 19:00 Uhr"
