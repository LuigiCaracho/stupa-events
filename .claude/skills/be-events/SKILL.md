---
name: be-events
description: Event domain of STUPA Events. Tables organization, category, event, event_revision, attachment, the poster upload with ClamAV scan and WebP derivatives, the public view public_event_v and the feed GET /api/public/feed/events with media. Use when working on event CRUD, organizations or categories, poster handling, scan and derive jobs, the public API or its DB role.
---

# Events, poster, public feed: `backend/app/modules/{orgs,taxonomy,events,dossier,publicapi}`

**Does:** Stores events as dossiers with revisions, handles the poster (the only attachment kind in M1) and serves
approved events with a poster to the public website.

## Key files

| File | Role |
|---|---|
| `migrations/versions/0002_events_core.py` | all event tables, CHECKs, triggers, `public_event_v`, reference seeds |
| `events/models.py`, `states.py` | ORM `Event`, `EventState` (8 values), `PublicStatus` |
| `events/schemas.py` | `EventCreate`, `EventPatch`, `EventOut` (camelCase, `extra=forbid`, aware datetimes) |
| `events/service.py` | T00 create and PATCH; optimistic `WHERE rev = :rev`; revision + audit in the same transaction |
| `events/access.py` | `load_visible` (404 outside scope), `visible_events_query`, `snapshot_of` for the guards |
| `events/revisions.py`, `presenter.py` | `event_revision` snapshots, ORM to `EventOut` incl. `allowedTransitions` |
| `orgs/scope.py`, `orgs/router.py` | slug-to-id binding, `org_ids_for`; `GET /api/organizations?creatable=true` |
| `taxonomy/reference.py`, `seeding.py`, `router.py` | organizations and categories as Python data (not YAML: the image has no `seeds/`); `GET /api/categories` |
| `dossier/posters.py`, `router.py` | upload: MIME sniff, Pillow re-encode, private bucket, `pending`, supersede |
| `worker/scan.py`, `dossier/derive.py`, `media/derivatives.py` | ClamAV scan, then `derive_poster` writes `derivatives/<sha16>-<variant>.webp` |
| `publicapi/{db,router,service,schemas}.py` | own engine on `PUBLIC_DATABASE_URL`, feed and media, `PublicEventOut` only |
| `scripts/seed_dev.py`, `seeds/dev_events.yaml` | dev dossiers through the real services (idempotent by title) |

## Data model

- `event(id, slug, state, public_status, title, summary, description_md, starts_at, ends_at, tzid, all_day,
  starts_on, ends_on, organization_id, venue_text, primary_category_id, hero_attachment_id, image_exception JSONB
  {granted_by, reason, at}, origin_kind, rev, public_seq, created_by, submitted_by, approved_by, ...)`.
  CHECKs: `ends_at >= starts_at`, org required unless `idea`/`withdrawn`, no control characters,
  `all_day = (starts_on IS NOT NULL)`. Unique slug when set.
- `event_revision(event_id, rev UNIQUE together, snapshot, actor_id, ...)` and `event_status_event(from_state,
  to_state, transition_id, note, ...)`: append-only (trigger + grants).
- `attachment(id, event_id, kind, storage_key, display_name, storage_name, mime, size_bytes, sha256, scan_status,
  alt_text, credit, rights_basis, derivatives JSONB, supersedes_id, retired_at, ...)`; `event_id` has no FK in the ORM.
- `organization(slug, name, short, trusted, ...)`, `category(slug, name, kind format|fachschaft|partner, ...)`.
- `public_event_v`: rows in `live|followup|archived` with a clean poster and derivatives or a valid exception;
  allowlist columns incl. `organization_slug` (feed filter `org`), `hero_sha`, `hero_derivatives`, `hero_alt`,
  `hero_credit`. Owned by `events_migrator`, no `security_invoker`.

## API

Internal (session + CSRF): `GET /api/events` (`state`, `organizationId`, `q`, `limit`, `offset`; `Page<Event>`
scoped in SQL, sorted by `startsAt`), `POST /api/events` (201, `idea`), `GET/PATCH /api/events/{id}` (`rev` required;
409 `conflict`/`field_locked`), `POST /api/events/{id}/poster` (multipart `file`, `altText`, `credit`, `rightsBasis`;
201 `pending`), `GET /api/events/{id}/poster/file?variant=thumb400|card1200` (`Cache-Control: private`),
`POST /api/events/{id}/image-exception` (editor, reason >= 10 chars), `GET /api/organizations?creatable=true`,
`GET /api/categories`.

Public (no session, no cookie): `GET /api/public/feed/events` (`from`, `to`, `category`, `org` slugs, `limit`
1..500; schema 2 `{schema, generatedAt, items[]}`, ETag, 304, `Cache-Control: public, max-age=300,
stale-while-revalidate=60`), `GET /api/public/media/{sha16}-{variant}.webp` (immutable, 404 unless the derivative
belongs to a public event). Shapes: `docs/M1-KONTRAKT.md` 4.2 and 4.4, schema `tests/schema/feed-v2.json`.

## Gotchas

- `image.url` and the feed `url` use `PUBLIC_BASE_URL`; host-run dev sets it to `http://localhost:4200`.
- A poster counts only when `scan_status = clean` and `derivatives` exist; without a running worker (arq) and ClamAV
  it stays `pending` forever. Host-run worker: `uv run --env-file .env arq worker.main.WorkerSettings`
  (`worker/main.py` reads `REDIS_URL` and `ARQ_QUEUE_NAME` from the process env, not from pydantic `.env`).
- `uv run --env-file` rejects unquoted values with spaces; quote `OIDC_SCOPES` and `MAIL_FROM_NAME`.
- `events_public` sees only `public_*_v` views (stage 2 of `deploy/db/roles.sql`, run it after every migration).
- `CsrfMiddleware` must not set `XSRF-TOKEN` on `/api/public/*` (`test_public_no_set_cookie`).
- Behind nginx the API's own strict CSP and nginx's SPA CSP both arrive on `/api/*`; browsers apply both.
- Never put drafts, `event_status_event.note`, `image_exception`, creators or contacts in the feed.
- Replacing a poster sets `supersedes_id` and a new `sha256`, so media ids change; nothing is deleted.
- Lists filter by `org_ids_for` in SQL; a foreign dossier is 404.

**Tests:** `tests/unit/events/*`, `tests/unit/publicapi/*`, `tests/integration/events/{test_flow,test_poster,
test_locking_and_fields,test_edges}.py`, `tests/integration/publicapi/test_public_feed.py`,
`tests/integration/test_db_grants_roles_sql.py` (real `roles.sql`), `tests/integration/orgs/*`.

**Siblings:** `be-pipeline`, `be-auth`, `deploy` (buckets, roles, nginx).
