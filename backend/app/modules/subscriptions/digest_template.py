"""Weekly digest mail: subject and HTML body, rendered in a Jinja sandbox.

Listmonk reads the body as a Go template, so every inserted value is HTML-escaped first and its
`{{` and `}}` become character references: an event title like `{{ .Subscriber.Email }}` stays
text. Only the footer carries a real placeholder (`{{ UnsubscribeURL }}`). Times are shown as
Berlin wall time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup, escape

from app.shared.timeutil import DEFAULT_TZID

SUBJECT = "STUPA Events: Das ist diese Woche los"
UNSUBSCRIBE_TAG = Markup("{{ UnsubscribeURL }}")
_WEEKDAYS = ("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So.")

_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True)
_TEMPLATE = _env.from_string(
    """<div style="font-family:sans-serif;max-width:560px;margin:0 auto">
<h1 style="font-size:20px">Das ist diese Woche los</h1>
<p>{{ week }}</p>
{% for e in events %}
<div style="border:1px solid #ccc;border-radius:8px;padding:12px;margin:12px 0">
<p style="margin:0;color:#555">{{ e.when }}{% if e.category %} · {{ e.category }}{% endif %}</p>
<h2 style="font-size:17px;margin:4px 0"><a href="{{ e.url }}">{{ e.title }}</a></h2>
{% if e.venue %}<p style="margin:0">{{ e.venue }}</p>{% endif %}
</div>
{% endfor %}
<p style="font-size:13px;color:#555">
Alle Termine: <a href="{{ all_url }}">{{ all_url }}</a><br>
Keine Mails mehr? <a href="{{ unsubscribe }}">Abmelden</a> geht mit einem Klick.
Mehr zu deinem Abo: <a href="{{ subs_url }}">{{ subs_url }}</a></p>
</div>
"""
)


@dataclass(frozen=True, slots=True)
class DigestEvent:
    """The public fields of one event the digest shows."""

    slug: str
    title: str
    starts_at: datetime
    all_day: bool
    venue: str | None
    category: str | None


def go_safe(value: str) -> Markup:
    """Escape for HTML and defuse Go template delimiters."""
    text = str(escape(value)).replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")
    return Markup(text)


def when(starts_at: datetime, all_day: bool) -> str:
    """Format the start as Berlin wall time: `Fr., 24.10., 19:00 Uhr` or `Fr., 24.10.`."""
    local = starts_at.astimezone(ZoneInfo(DEFAULT_TZID))
    day = f"{_WEEKDAYS[local.weekday()]}, {local:%d.%m.}"
    return day if all_day else f"{day}, {local:%H:%M} Uhr"


def render_digest(events: list[DigestEvent], *, base_url: str, week_start: date) -> str:
    """Render the HTML body for a list of events.

    Args:
        events: Events of the week, already sorted.
        base_url: Public base URL without a trailing slash.
        week_start: Monday of the week.

    Returns:
        The HTML body with the Listmonk placeholder `{{ UnsubscribeURL }}` in the footer.
    """
    root = base_url.rstrip("/")
    rows = [
        {
            "when": go_safe(when(e.starts_at, e.all_day)),
            "category": go_safe(e.category) if e.category else None,
            "title": go_safe(e.title),
            "venue": go_safe(e.venue) if e.venue else None,
            "url": go_safe(f"{root}/e/{e.slug}"),
        }
        for e in events
    ]
    return _TEMPLATE.render(
        events=rows,
        week=f"Woche ab {week_start:%d.%m.%Y}",
        all_url=go_safe(root),
        subs_url=go_safe(f"{root}/abos"),
        unsubscribe=UNSUBSCRIBE_TAG,
    )
