"""Shell pieces without a database: head goldens, JSON-LD, meta text, sitemap, robots."""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.modules.publicapi.query import cards
from app.modules.publicapi.shell import jsonld, meta, page, sitemap
from tests.unit.publicapi.test_public_unit import row

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "shell"
INDEX = (Path(__file__).resolve().parents[2] / "fixtures" / "spa-index.html").read_text()
BASE = "https://events.example"
SHA = "3fa9c1d2e4b5a678" + "0" * 48
STARTS = datetime(2026, 10, 22, 18, 0, tzinfo=UTC)
ENDS = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)
DERIVATIVES = {
    "thumb_400": {"id": "aa-thumb_400", "width": 400, "height": 225},
    "card_1200": {"id": "aa-card_1200", "width": 1200, "height": 675},
    "og_1200x630": {"id": "aa-og_1200x630", "width": 1200, "height": 630},
}


def event(**over: Any) -> Any:
    base = {
        "starts_at": STARTS,
        "ends_at": ENDS,
        "hero_derivatives": DERIVATIVES,
        "ticket_url": None,
        "description_md": "Text",
    }
    return row(**{**base, **over})


def golden(name: str, body: str) -> None:
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(body)
    assert body == path.read_text()


def test_head_goldens() -> None:
    scheduled = meta.event_page(event(ticket_url="https://t.example/x"), BASE)
    golden("event-scheduled.html", page.render(INDEX, scheduled, BASE))
    cancelled = meta.event_page(event(public_status="cancelled", public_reason_text="Regen"), BASE)
    golden("event-cancelled.html", page.render(INDEX, cancelled, BASE))
    plain = meta.event_page(event(hero_sha=None, hero_derivatives=None, summary=None), BASE)
    golden("event-no-image.html", page.render(INDEX, plain, BASE))
    upcoming = [cards.to_card(event())]
    golden(
        "category.html",
        page.render(INDEX, meta.category_page("kino", "Kino", "Filmabende", BASE, upcoming), BASE),
    )
    golden("home.html", page.render(INDEX, meta.home_page(BASE, upcoming), BASE))


def test_the_title_and_description_are_replaced_once() -> None:
    html = page.render(INDEX, meta.event_page(event(), BASE), BASE)
    assert html.count("<title>") == 1 and html.count('name="description"') == 1
    assert "Veranstaltungen planen" not in html and html.count("</head>") == 1


def test_a_hostile_title_is_escaped_in_every_place() -> None:
    hostile = event(title='"><script>alert(1)</script>', summary="</script><img src=x>")
    html = page.render(INDEX, meta.event_page(hostile, BASE), BASE)
    assert "<script>alert(1)" not in html and "<img src=x>" not in html
    block = re.search(r'ld\+json">(.*?)</script>', html, re.DOTALL)
    assert block and "<" not in block.group(1) and ">" not in block.group(1)
    assert json.loads(block.group(1))["name"] == hostile.title


def test_jsonld_statuses_offers_and_escapes() -> None:
    for status, url in (
        ("scheduled", "EventScheduled"),
        ("cancelled", "EventCancelled"),
        ("postponed", "EventPostponed"),
    ):
        assert jsonld.event_data(event(public_status=status), BASE)["eventStatus"].endswith(url)
    assert "offers" not in jsonld.event_data(event(), BASE)
    offer = jsonld.event_data(event(ticket_url="https://t.example/x"), BASE)["offers"]
    assert offer == {"@type": "Offer", "url": "https://t.example/x"}
    text = jsonld.serialize({"a": "<>&  "})
    assert all(c not in text for c in "<>&  ")
    assert json.loads(text) == {"a": "<>&  "}


def test_jsonld_place_dates_and_private_venue() -> None:
    data = jsonld.event_data(event(venue_address="Weg 1", venue_city="Reutlingen"), BASE)
    assert data["location"]["address"] == {
        "@type": "PostalAddress",
        "streetAddress": "Weg 1",
        "addressLocality": "Reutlingen",
    }
    assert data["startDate"] == "2026-10-22T20:00:00+02:00"
    assert data["image"] == [f"{BASE}/api/public/media/aa-og_1200x630.webp"]
    private = jsonld.event_data(event(venue_name="Treffpunkt auf Anfrage"), BASE)
    assert "location" not in private
    day = jsonld.event_data(
        event(all_day=True, starts_on=date(2026, 10, 22), ends_on=date(2026, 10, 23)), BASE
    )
    assert day["startDate"] == "2026-10-22" and day["endDate"] == "2026-10-23"


def test_description_has_date_place_summary_and_stays_short() -> None:
    text = meta.event_page(event(summary="Ein Film. " * 40), BASE).description
    assert text.startswith("Do., 22. Okt. 2026, 20:00 · Kinosaal. Ein Film.")
    assert len(text) <= 200 and text.endswith("…")
    day = meta.event_page(event(all_day=True), BASE).description
    assert day.startswith("Do., 22. Okt. 2026 ·")


def test_the_status_prefix_and_the_default_image() -> None:
    cancelled = meta.event_page(event(public_status="cancelled", hero_sha=None), BASE)
    assert cancelled.title == "Abgesagt: Movienight"
    assert cancelled.image == f"{BASE}/og-default.png"
    assert meta.event_page(event(public_status="postponed"), BASE).title.startswith("Verschoben: ")


def test_the_missing_index_is_a_503(tmp_path: Path) -> None:
    from app.shared.errors import ServiceUnavailableError

    with pytest.raises(ServiceUnavailableError):
        page.load_index(str(tmp_path / "nope.html"))


def test_the_index_is_read_again_when_it_changes(tmp_path: Path) -> None:
    path = tmp_path / "index.html"
    path.write_text("one")
    assert page.load_index(str(path)) == "one"
    path.write_text("two")
    os.utime(path, (1, 1))
    assert page.load_index(str(path)) == "two"


def test_the_shell_csp_equals_the_nginx_snippet() -> None:
    conf = Path(__file__).resolve().parents[4] / "deploy" / "web" / "security-headers.conf"
    nginx = re.search(r'Content-Security-Policy "([^"]+)"', conf.read_text())
    assert nginx and nginx.group(1) == page.SPA_CSP


def test_sitemap_is_wellformed_and_capped(caplog: pytest.LogCaptureFixture) -> None:
    updated = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
    events = [(f"e-{n}", updated) for n in range(10)]
    body = sitemap.build(BASE, events, ["kino", "party"], limit=10)
    ns = {"s": sitemap.NAMESPACE}
    locs = [e.text for e in ET.fromstring(body).findall("s:url/s:loc", ns)]
    assert len(locs) == 10 and locs[0] == f"{BASE}/" and f"{BASE}/k/kino" in locs
    assert "snapshot_too_large" in caplog.text
    full = sitemap.build(BASE, events, ["kino"])
    assert b"<lastmod>2026-10-01T09:30:00Z</lastmod>" in full and len(full) > len(body)
    assert full.startswith(b"<?xml")


def test_robots_lists_the_sitemap_and_forbids_the_api() -> None:
    body = sitemap.robots("https://x.example/").decode()
    assert "Disallow: /api/" in body and body.endswith("Sitemap: https://x.example/sitemap.xml\n")
