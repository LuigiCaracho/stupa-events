"""The HTML shell: head block, Open Graph, JSON-LD, 404, headers, sitemap and robots."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest

from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.site_data import BASE, Site

pytestmark = pytest.mark.integration
JSONLD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


@pytest.fixture
async def site(api: Api) -> Site:
    site_data.configure(api)
    return await site_data.seed(api)


def tag(html: str, prop: str) -> str:
    found = re.search(rf'<meta property="{prop}" content="([^"]*)">', html)
    assert found, prop
    return found.group(1)


async def page(api: Api, path: str, **kw: object):  # noqa: ANN202
    return await api.request(None, "GET", path, **kw)


async def test_event_page_has_open_graph_canonical_calendar_and_jsonld(
    api: Api, site: Site
) -> None:
    slug = site.slugs["movie"]
    response = await page(api, f"/e/{slug}")
    html = response.text
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    assert "<title>Movienight Kinoabend</title>" in html
    assert (
        tag(html, "og:title") == "Movienight Kinoabend"
        and tag(html, "og:url") == f"{BASE}/e/{slug}"
    )
    assert tag(html, "og:image").startswith(f"{BASE}/api/public/media/")
    assert tag(html, "og:image").endswith("-og_1200x630.webp")
    assert tag(html, "og:image:width") == "1200" and tag(html, "og:locale") == "de_DE"
    assert f'<link rel="canonical" href="{BASE}/e/{slug}">' in html
    assert f'href="{BASE}/ics/e/{slug}.ics"' in html and f'href="{BASE}/ics/all.ics"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert html.count('name="description"') == 1 and "Veranstaltungen planen" not in html
    data = json.loads(JSONLD.search(html).group(1))  # type: ignore[union-attr]
    assert data["@type"] == "Event" and data["eventStatus"] == "https://schema.org/EventScheduled"
    assert data["offers"] == {"@type": "Offer", "url": "https://tickets.example/x"}
    assert data["location"]["name"] == "Kinosaal 9-133" and data["startDate"].endswith(
        ("+01:00", "+02:00")
    )
    assert "<noscript><h1>Movienight Kinoabend</h1>" in html
    assert "main-TEST1234.js" in html


async def test_event_without_poster_or_ticket_uses_the_default_image(api: Api, site: Site) -> None:
    html = (await page(api, f"/e/{site.slugs['karaoke']}")).text
    assert tag(html, "og:image") == f"{BASE}/og-default.png"
    assert "offers" not in JSONLD.search(html).group(1)  # type: ignore[union-attr]


async def test_cancelled_event_is_prefixed_and_marked(api: Api, site: Site) -> None:
    html = (await page(api, f"/e/{site.slugs['ski']}")).text
    assert tag(html, "og:title") == "Abgesagt: Skiausfahrt"
    assert "EventCancelled" in html


async def test_unknown_and_hidden_events_get_the_spa_with_404_and_noindex(
    api: Api, site: Site
) -> None:
    for slug in ("nope", site.slugs["draft"], site.slugs["gone"], "Bad_Slug"):
        response = await page(api, f"/e/{slug}")
        assert response.status_code == 404, slug
        assert 'name="robots" content="noindex"' in response.text and "<app-root>" in response.text
        assert "Geheimer Entwurf" not in response.text
        assert response.headers["cache-control"] == "no-cache"
    assert (await page(api, "/k/nope")).status_code == 404


async def test_fixed_pages_category_and_headers(api: Api, site: Site) -> None:
    home = await page(api, "/")
    assert home.status_code == 200 and "<title>Heute am Campus · STUPA Events</title>" in home.text
    assert "Movienight Kinoabend" in home.text
    search = await page(api, "/suche", params={"q": "geheim"})
    assert "geheim" not in search.text and "<title>Suche · STUPA Events</title>" in search.text
    category = await page(api, "/k/kino")
    assert "<title>Kino · STUPA Events</title>" in category.text
    assert tag(category.text, "og:description") == "Movienight und Filmabende"
    assert f'href="{BASE}/ics/k/kino.ics"' in category.text
    for response in (
        home,
        search,
        category,
        await page(api, "/kalender"),
        await page(api, "/rueckblick"),
    ):
        h = response.headers
        assert h["cache-control"] == "public, max-age=60, stale-while-revalidate=30"
        assert h["etag"].startswith('"') and "set-cookie" not in h
        assert h["content-security-policy"].startswith("default-src 'self'")
        assert "x-robots-tag" not in h


async def test_same_bytes_for_every_user_agent_and_304(api: Api, site: Site) -> None:
    url = f"/e/{site.slugs['movie']}"
    bodies = set()
    for agent in (
        "WhatsApp/2.24.1",
        "Synapse (bot; +https://github.com/element-hq/synapse)",
        "facebookexternalhit/1.1",
        "Signal-Desktop/7.0",
        "Mozilla/5.0",
    ):
        bodies.add((await page(api, url, headers={"User-Agent": agent})).content)
    assert len(bodies) == 1
    first = await page(api, url)
    again = await page(api, url, headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b""


async def test_a_hostile_title_is_escaped_everywhere(api: Api, site: Site) -> None:
    await site_data.add(
        api,
        site,
        "xss",
        title='"><script>alert(1)</script>',
        summary="</script><b>x</b>",
        **site_data.at(30),
    )
    html = (await page(api, f"/e/{site.slugs['xss']}")).text
    assert "<script>alert(1)" not in html and "</script><b>" not in html
    block = JSONLD.search(html).group(1)  # type: ignore[union-attr]
    assert "<" not in block and json.loads(block)["name"] == '"><script>alert(1)</script>'


async def test_sitemap_lists_public_events_and_categories_once(api: Api, site: Site) -> None:
    response = await page(api, "/sitemap.xml")
    assert response.headers["content-type"].startswith("application/xml")
    assert response.headers["cache-control"] == "public, max-age=3600"
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.fromstring(response.content).findall("s:url/s:loc", ns)]
    assert len(locs) == len(set(locs))
    for key in ("movie", "karaoke", "fsi", "cafe", "ski", "past"):
        assert f"{BASE}/e/{site.slugs[key]}" in locs
    for key in ("draft", "gone"):
        assert f"{BASE}/e/{site.slugs[key]}" not in locs
    assert f"{BASE}/k/kino" in locs and f"{BASE}/rueckblick" in locs
    assert re.search(r"<lastmod>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ</lastmod>", response.text)


async def test_robots_txt_wording(api: Api, site: Site) -> None:
    body = (await page(api, "/robots.txt")).text
    assert body == (
        "User-agent: *\nAllow: /e/\nAllow: /k/\nAllow: /suche\nDisallow: /api/\n"
        "Disallow: /ics/\nDisallow: /dossiers\nDisallow: /verwaltung\nDisallow: /konto\n"
        f"Disallow: /login\nSitemap: {BASE}/sitemap.xml\n"
    )


async def test_missing_spa_build_is_a_problem_503(api: Api, site: Site) -> None:
    site_data.configure(api, spa_index_path="/nonexistent/index.html")
    response = await page(api, "/")
    assert response.status_code == 503 and response.json()["code"] == "spa_not_built"
