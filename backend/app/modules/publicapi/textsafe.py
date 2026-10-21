"""`description_md` to sanitized HTML for the feed field `textHtml` (contract 9.4, M3 12.24).

CommonMark without raw HTML, then `nh3` with a short allowlist of tags and a `rel` on links.
Headings, images, tables and code lose their tags and keep their text. This is the second
net behind E07 (a new link host is a critical change at approval): even a link that slipped
through cannot carry a script, a `data:` URI or a protocol-relative target.
"""

from __future__ import annotations

import nh3
from markdown_it import MarkdownIt

TAGS = {"p", "a", "strong", "em", "ul", "ol", "li", "br"}
SCHEMES = {"http", "https", "mailto"}
LINK_REL = "noopener noreferrer nofollow"
LINK_PREFIXES = ("http://", "https://", "mailto:")
_MARKDOWN = MarkdownIt("commonmark", {"html": False, "typographer": False})


def _only_absolute_links(tag: str, attribute: str, value: str) -> str | None:
    """Keep an `href` that starts with an allowed scheme; relative and `//host` links go."""
    if attribute != "href":
        return value
    return value if value.strip().lower().startswith(LINK_PREFIXES) else None


def text_html(markdown: str | None) -> str | None:
    """Render and sanitize `markdown`; an empty text gives `None`."""
    if not markdown or not markdown.strip():
        return None
    rendered = _MARKDOWN.render(markdown)
    clean = nh3.clean(
        rendered,
        tags=TAGS,
        attributes={"a": {"href"}},
        url_schemes=SCHEMES,
        attribute_filter=_only_absolute_links,
        link_rel=LINK_REL,
        strip_comments=True,
    ).strip()
    return clean or None
