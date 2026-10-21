"""The allowlist of everything the public API may show (E14, E39).

`PUBLIC_FIELDS` names, per public model, the exact fields it may carry; `PUBLIC_VIEW_COLUMNS`
names the columns of `public_event_v`. Both are compared with the code by tests: a new field
or column fails them until it is added here, and this file has a CODEOWNERS entry. Adding a
name here is a decision about publishing data, so it needs a review.
"""

from __future__ import annotations

from collections.abc import Mapping

PUBLIC_FIELDS: Mapping[str, frozenset[str]] = {
    "PublicOrganization": frozenset({"id", "slug", "name", "short"}),
    "PublicCategory": frozenset({"slug", "name", "kind"}),
    "PublicFormat": frozenset({"slug", "title"}),
    "PublicVenue": frozenset({"name", "address", "city"}),
    "PublicImage": frozenset({"url", "width", "height", "alt", "credit"}),
    "PublicStatusReason": frozenset({"code", "text"}),
    "PublicEventOut": frozenset(
        {
            "id",
            "slug",
            "title",
            "summary",
            "starts_at",
            "ends_at",
            "all_day",
            "starts_on",
            "ends_on",
            "tzid",
            "status",
            "organization",
            "venue_text",
            "venue",
            "status_reason",
            "categories",
            "format",
            "image",
            "ticket_url",
            "website_url",
            "cost_text",
            "text_html",
            "sequence",
            "updated_at",
            "url",
        }
    ),
    "FeedOut": frozenset({"schema_version", "generated_at", "next_cursor", "items"}),
    "IcsRow": frozenset(
        {
            "id",
            "slug",
            "title",
            "summary",
            "starts_at",
            "ends_at",
            "all_day",
            "starts_on",
            "ends_on",
            "tzid",
            "public_status",
            "public_seq",
            "updated_at",
            "public_reason_text",
            "venue_name",
            "venue_address",
            "venue_city",
            "category_slug",
            "category_name",
            "category_parent_slug",
            "category_parent_name",
        }
    ),
}

PUBLIC_VIEW_COLUMNS: tuple[str, ...] = (
    "id",
    "slug",
    "title",
    "summary",
    "starts_at",
    "ends_at",
    "all_day",
    "tzid",
    "public_status",
    "organization_id",
    "organization_slug",
    "organization_name",
    "organization_short",
    "venue_text",
    "category_slug",
    "category_name",
    "category_kind",
    "hero_sha",
    "hero_derivatives",
    "hero_alt",
    "hero_credit",
    "updated_at",
    "public_reason_code",
    "public_reason_text",
    "starts_on",
    "ends_on",
    "public_seq",
    "category_parent_slug",
    "category_parent_name",
    "category_parent_kind",
    "format_slug",
    "format_title",
    "venue_name",
    "venue_address",
    "venue_city",
    "ticket_url",
    "website_url",
    "cost_text",
    "description_md",
)

PUBLIC_CATEGORY_COLUMNS: tuple[str, ...] = ("slug", "name", "kind", "parent_slug")
