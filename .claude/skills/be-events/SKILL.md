---
name: be-events
description: Event domain of STUPA Events. Tables organization, category, event, event_revision, event_status_event, editor_draft, attachment, the poster upload with ClamAV scan and WebP derivatives, the public view public_event_v and the feed GET /api/public/feed/events with media. Use when working on event CRUD, organizations or categories, poster handling, scan and derive jobs, the public API or its DB role.
---

# Events, poster, public feed: `backend/app/modules/{orgs,taxonomy,events,dossier,publicapi}`

**Does:** Stores events as dossiers with revisions, handles the poster (optional since M5b, but shown first) and
serves published and archived events to the public website (`image: null` without a poster).

## Key files

| File | Role |
|---|---|
| `migrations/versions/0002_events_core.py` | all event tables, CHECKs, triggers, `public_event_v`, reference seeds |
| `events/models.py`, `states.py` | ORM `Event`, `EventState` (`draft`, `published`, `archived`), `PublicStatus` |
| `events/schemas.py` | `EventCreate` (`organizationId` required, 404 outside the `event.create` scope), `EventPatch`, `DraftFields`, `EventOut` (camelCase, `extra=forbid`, aware datetimes) |
| `events/service.py`, `writer.py` | create a draft and PATCH (rules in `editing.py`, skill `be-lifecycle`); `update_event` is the optimistic `WHERE rev = :rev` |
| `events/{cards,listing,calendar}.py`, `card_schemas.py` | `EventCard` (`hasPoster`, `publicStatus`, `howtoUnverified`, `hintCount`), list and calendar queries with SQL filters |
| `events/{drafts,drafts_router}.py` | autosave `PUT/GET/DELETE /events/{id}/draft` (`editor_draft`, 14 days) |
| `events/{revision_views,revisions_router}.py`, `conflict.py` | revision list/detail with `changedFields`; ETag, `If-Match`, 409 with `current` |
| `events/access.py` | `load_visible` (404 outside scope), `visible_events_query` |
| `events/revisions.py`, `presenter.py` | `event_revision` snapshots, ORM to `EventOut` incl. `allowedActions`, `editableFields`, `hintCount` |
| `orgs/scope.py`, `orgs/router.py` | slug-to-id binding, `org_ids_for`; `GET /api/organizations?creatable=true` |
| `taxonomy/reference.py`, `reference_m2.py`, `venue_reference.py`, `seeding.py` | organizations, categories and the 44 venues as Python data (not YAML: the image has no `seeds/`); `reference_m2` holds the M2 renames |
| `taxonomy/router.py` | `GET /api/categories` (`?tree=true`), `GET /api/venues` (a private venue shows no address) |
| `admin/*_router.py` | `/api/admin/organizations|categories|venues` (no DELETE, `active=false` hides), see `docs/M2-KONTRAKT.md` |
| `dossier/posters.py`, `router.py` | upload: MIME sniff, Pillow re-encode, private bucket, `pending`, supersede |
| `worker/scan.py`, `dossier/derive.py`, `media/derivatives.py` | ClamAV scan, then `derive_poster` writes `derivatives/<sha16>-<variant>.webp` |
| `publicapi/{db,router,service,schemas}.py` | own engine on `PUBLIC_DATABASE_URL`, feed and media, `PublicEventOut` only |
| `scripts/seed_dev.py`, `seeds/dev_events.yaml` | dev dossiers in the three states, through the real services (idempotent by title); `scripts/seed_docs.py` adds format, outcome, retrospective and howto |

## Data model

- `event(id, slug, state, public_status, title, summary, description_md, starts_at, ends_at, tzid, all_day,
  starts_on, ends_on, organization_id, venue_text, primary_category_id, hero_attachment_id, origin_kind, rev,
  public_seq, created_by, ...)`.
  CHECKs: `ends_at >= starts_at`, org required unless `draft`, `tzid = 'Europe/Berlin'`, no control characters,
  `all_day = (starts_on IS NOT NULL)`. Unique slug when set.
- `event_revision(event_id, rev UNIQUE together, snapshot, actor_id, ...)` and `event_status_event(from_state,
  to_state, transition_id, note, ...)`: append-only (trigger + grants).
- `attachment(id, event_id, kind, storage_key, display_name, storage_name, mime, size_bytes, sha256, scan_status,
  alt_text, credit, rights_basis, derivatives JSONB, supersedes_id, retired_at, ...)`; `event_id` has no FK in the ORM.
- `organization(slug, name, short, ...)`, `category(slug, name, kind format|fachschaft|partner, ...)`.
- `public_event_v` (0007): rows in `published|archived` with a slug; the poster columns are a `LEFT JOIN` on
  `attachment_poster_ok` (clean, not retired, three derivatives, consent when persons are depicted), else NULL;
  allowlist columns incl. `organization_slug` (feed filter `org`, also `organization.slug` in the feed object), `hero_sha`, `hero_derivatives`, `hero_alt`,
  `hero_credit`. Owned by `events_migrator`, no `security_invoker`.

## API

Internal (session + CSRF): `GET /api/events` (`view=list|calendar`, `state`, `organization` slug, `category` slug,
`mine`, `q`, `from`, `to`, `sort`, `limit`, `offset`; `Page<EventCard>` or `CalendarOut`, scoped in SQL),
`POST /api/events` (201, `draft`), `GET/PATCH /api/events/{id}` (ETag; PATCH takes
`If-Match` or `rev`; 409 `conflict`/`field_locked`, 428; `organizationId` only by the editorial team while empty), `POST /api/events/{id}/poster` (multipart `file`, `altText`, `credit`, `rightsBasis`;
201 `pending`), `GET /api/events/{id}/poster/file?variant=thumb400|card1200` (`Cache-Control: private`),
`GET /api/events/{id}/hints`, the lifecycle routes (skill `be-lifecycle`),
`GET /api/organizations?creatable=true`, `GET /api/categories`, `GET /api/events/{id}/revisions[/{rev}]`.

Public (no session, no cookie): `GET /api/public/feed/events` (`from`, `to`, `since`, `category`, `organization`/`org` slugs, `cursor`, `limit`
1..500; schema 2 `{schema, generatedAt, items[]}`, ETag, 304, `Cache-Control: public, max-age=300,
stale-while-revalidate=60`), `GET /api/public/media/{sha16}-{variant}.webp` (immutable, 404 unless the derivative
belongs to a public event). Shapes: `docs/M1-KONTRAKT.md` 4.2 and 4.4 and `docs/M5-KONTRAKT.md` 9 (see skill `be-public`), schema `tests/schema/feed-v2.json`.
Since M5 an event also has `format_id`, `derived_from_id`, `outcome`, `facts`, `location_precision` (a free `venue_text` is public only after `confirm-location`), all-day columns are writable and `view=calendar` exists on `GET /events`.

## Gotchas

- `image.url` and the feed `url` use `PUBLIC_BASE_URL`; host-run dev sets it to `http://localhost:4200`.
- A poster counts only when `scan_status = clean` and `derivatives` exist; without a running worker (arq) and ClamAV
  it stays `pending` forever. Host-run worker: `uv run --env-file .env arq worker.main.WorkerSettings`
  (`worker/main.py` reads `REDIS_URL` and `ARQ_QUEUE_NAME` from the process env, not from pydantic `.env`).
- `uv run --env-file` rejects unquoted values with spaces; quote `OIDC_SCOPES` and `MAIL_FROM_NAME`.
- `events_public` sees only `public_*_v` views (stage 2 of `deploy/db/roles.sql`, run it after every migration).
- `CsrfMiddleware` must not set `XSRF-TOKEN` on `/api/public/*` (`test_public_no_set_cookie`).
- Behind nginx the API's own strict CSP and nginx's SPA CSP both arrive on `/api/*`; browsers apply both.
- Never put drafts, `event_status_event.note`, creators or contacts in the feed.
- Replacing a poster sets `supersedes_id` and a new `sha256`, so media ids change; nothing is deleted.
- Lists filter by `org_ids_for` in SQL; a foreign dossier is 404. Old drafts without an organization (pre-0007
  proposals) are visible to the editorial team only, which assigns one by `PATCH`.
- The feed carries `status` and `statusReason` for cancelled or postponed events; the venue name comes from `venue`
  (`NULL` for a private venue).
- `editor_draft` has no FK and is wiped by `purge_drafts` after 14 days; no role reads another person's draft.

**Dossier and knowledge (M4, `docs/M4-KONTRAKT.md`):** `modules/files` (upload rules in `attachment_types.py`, one write path
`attachments.py`, pure visibility table `access.py`), `modules/dossier` (documents with `If-Match`, checklist, comments,
quotes, mail template facade, worker jobs `build_preview` and `promote_poster`), `modules/media/router.py`
and `ref_sync.py`. A poster of a published dossier stays the hero until `promote_poster` swaps it after scan and derivatives.
Quotes, business plans and contracts are never `shared` (CHECK) and only readable with `event.edit`/`event.read_all`/
`dossier.read_restricted`; amounts live in `quote` only. `events/writer.update_event` recomputes checklist due dates
when `starts_at` changes and records description images in `media_ref`. Tests: `tests/integration/dossier/*`,
`tests/unit/{files,dossier}/*`; helpers `tests/_support/samples.py`.

**Tests:** `tests/integration/events/{test_revisions_api,test_visibility,test_autosave}.py`, `tests/unit/events/*`, `tests/unit/publicapi/*`, `tests/integration/events/{test_flow,test_poster,
test_locking_and_fields,test_edges}.py`, `tests/integration/publicapi/test_public_feed.py`,
`tests/integration/test_db_grants_roles_sql.py` (real `roles.sql`), `tests/integration/orgs/*`.

**Siblings:** `be-lifecycle`, `be-auth`, `deploy` (buckets, roles, nginx).
