---
name: be-public
description: The public side of STUPA Events (M5): feed schema 2 with cursor and since, the ICS calendars /ics/all.ics and /ics/k/<slug>.ics, the worker snapshots in Redis, the public allowlist, the canary test and Schemathesis. Use when changing public fields, public_event_v, the feed, a calendar, the snapshot or anything the anonymous API shows.
---

# Public API: `app/modules/publicapi`, `worker/public_cache.py`

**Does:** Serves what the website and calendar apps read, with the role `events_public` on `public_event_v` and
`public_category_v` only (E14). Contract: `docs/M5-KONTRAKT.md` sections 8 to 10.

## Key files

| File | Role |
|---|---|
| `allowlist.py` | `PUBLIC_FIELDS` per public model and `PUBLIC_VIEW_COLUMNS` (CODEOWNERS); `test_feed_v2_units.py` compares them with the code |
| `schemas.py`, `service.py` | `PublicEventOut` built field by field from view rows; live selection with the filters; ETag over items and cursor |
| `selection.py`, `cursor.py` | the same filters in Python for snapshots; `base64url{startsAt,id}` cursor |
| `serving.py`, `cache.py` | snapshot first (`events:public:snap:<name>`, version must equal `events:feed:version`), else live and `request_rebuild` |
| `ics/` | `writer.py` (fixed order, CRLF, TZID + VTIMEZONE, repeated hour in UTC), `fold.py`, `escape.py`, `timezone.py`, `rows.py` |
| `ics_router.py`, `router.py` | `/ics/*` (no `/api` prefix), `/api/public/feed/events`, media |
| `textsafe.py` | `description_md` to HTML: markdown-it without HTML, `nh3` allowlist, only absolute http/https/mailto links |
| `worker/public_cache.py` | `rebuild_public_cache` (queued with `_job_id=public_cache`, cron minute 5): reads the version first, writes all snapshots in one MULTI |

## Gotchas

- A new public field needs: view column (migration), `PUBLIC_EVENT_V` in `service.py`, `PublicEventOut`, `allowlist.py`,
  `feed-v2.json`, and the canary stays green. `/ics/*` is a public prefix for the middleware (`is_public_path`).
- `venue_text` in the view is `NULL` for private venues and for a free text that no approver confirmed.
- ICS golden files: `UPDATE_GOLDEN=1 pytest tests/unit/publicapi/test_ics.py`, then read the diff by hand.
- Schemathesis (`test_schemathesis.py`) draws 200 cases per operation and mode and sends them through the integration client.
- Redis keys: `events:feed:version` (counter) and `events:public:snap:<name>` (hash, 2 h lifetime). The job queues
  with `keep_result=0`, otherwise arq refuses a new job with the same id for an hour.
