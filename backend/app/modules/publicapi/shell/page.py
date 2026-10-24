"""Fill the built SPA `index.html` with the head block and the noscript list of a `Page`.

The index is read from `SPA_INDEX_PATH` and kept in the process until its mtime changes.
Only `<title>` and the description meta change; the block with canonical, Open Graph, calendar
links and JSON-LD goes in before `</head>`, the noscript list before `</body>`. Jinja2 with
autoescape builds all markup, nothing is concatenated by hand. The page does not depend on the
user agent: a chat preview bot and a browser get the same bytes.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from app.modules.publicapi.shell.meta import SITE, Page
from app.shared.errors import ServiceUnavailableError

SPA_CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'; object-src 'none'"
)
HTML_HEADERS = {
    "Content-Security-Policy": SPA_CSP,
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
}
_TITLE = re.compile(r"<title>.*?</title>", re.DOTALL | re.IGNORECASE)
_ATTRIBUTES = r"""(?:[^>"']|"[^"]*"|'[^']*')*"""
_DESCRIPTION = re.compile(
    rf"""<meta\b(?={_ATTRIBUTES}\bname\s*=\s*["']description["']){_ATTRIBUTES}>""", re.IGNORECASE
)
_env = Environment(autoescape=True)
_HEAD = _env.from_string(
    """<meta name="description" content="{{ p.description }}">
<link rel="canonical" href="{{ canonical }}">
{% if p.noindex %}<meta name="robots" content="noindex">
{% endif %}<meta property="og:type" content="website">
<meta property="og:site_name" content="{{ site }}">
<meta property="og:locale" content="de_DE">
<meta property="og:title" content="{{ p.title }}">
<meta property="og:description" content="{{ p.description }}">
<meta property="og:url" content="{{ canonical }}">
<meta property="og:image" content="{{ p.image }}">
<meta property="og:image:width" content="{{ p.image_size[0] }}">
<meta property="og:image:height" content="{{ p.image_size[1] }}">
<meta property="og:image:alt" content="{{ p.image_alt }}">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="text/calendar" href="{{ base }}/ics/all.ics" title="Alle Events">
{% for c in p.calendars %}<link rel="alternate" type="text/calendar" href="{{ base }}{{ c.href }}"
 title="{{ c.label }}">
{% endfor %}{% if p.jsonld %}<script type="application/ld+json">{{ p.jsonld|safe }}</script>
{% endif %}"""
)
_NOSCRIPT = _env.from_string(
    "<noscript>"
    "{% if p.heading %}<h1>{{ p.heading }}</h1>{% endif %}"
    "{% for fact in p.facts %}<p>{{ fact }}</p>{% endfor %}"
    "{% if p.summary %}<p>{{ p.summary }}</p>{% endif %}"
    "{% if p.ticket %}"
    '<p><a href="{{ p.ticket }}" rel="noopener noreferrer nofollow">Tickets</a></p>'
    "{% endif %}"
    "{% if p.items %}<ul>"
    '{% for i in p.items %}<li><a href="{{ i.href }}">{{ i.label }}</a></li>{% endfor %}'
    "</ul>{% endif %}"
    "</noscript>"
)
_cache: dict[str, tuple[float, str]] = {}


def load_index(path: str) -> str:
    """Read the built `index.html`, memoized by mtime.

    Raises:
        ServiceUnavailableError: `spa_not_built` when the file is missing.
    """
    try:
        mtime = Path(path).stat().st_mtime
        cached = _cache.get(path)
        if cached is None or cached[0] != mtime:
            cached = (mtime, Path(path).read_text(encoding="utf-8"))
            _cache[path] = cached
        return cached[1]
    except OSError as exc:
        raise ServiceUnavailableError(
            "Die Oberfläche ist nicht gebaut.", code="spa_not_built"
        ) from exc


def index_version(path: str) -> str:
    """Return the mtime of the built `index.html` ("" when missing) for keying cached shells."""
    try:
        return str(Path(path).stat().st_mtime_ns)
    except OSError:
        return ""


def render(index_html: str, page: Page, base_url: str) -> str:
    """Return the index with the head block and the noscript list of `page`."""
    base = base_url.rstrip("/")
    context = {"p": page, "base": base, "canonical": base + page.path, "site": SITE}
    html = _TITLE.sub(lambda _: f"<title>{Markup.escape(page.title)}</title>", index_html, count=1)
    html = _DESCRIPTION.sub("", html, count=1)
    html = html.replace("</head>", _HEAD.render(context) + "</head>", 1)
    return html.replace("</body>", _NOSCRIPT.render(context) + "</body>", 1)
