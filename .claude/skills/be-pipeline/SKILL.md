---
name: be-pipeline
description: The event state machine of STUPA Events. States, transitions T00 T01 T02 T04 T05 as data, guards (field_missing, start_in_past, image_required, four_eyes), PipelineService.stage_fire, optimistic locking, post-commit actions, the DB triggers enforce_publish_image and keep_published_poster, audit and revisions. Use when working on transitions, guards, who may publish, field locking or the reasons[] error shape.
---

# Pipeline: `backend/app/modules/pipeline`

**Does:** Moves an event through `idea`, `planning`, `in_review`, `approved`, `live`. `followup`, `archived` and
`withdrawn` exist in the enum and the DB CHECK; their transitions (T03, T06 to T12) arrive in M3, and the route
only accepts `Literal["T01","T02","T04","T05"]` (else 422 `validation_error`).

## Key files

| File | Role |
|---|---|
| `transitions.py` | `TRANSITIONS` table (source, target, permission, guards, `own_only`, `sets`, `actions`), pure `decide`, `allowed_transitions` |
| `guards.py` | pure guards `(snapshot, actor, now) -> list[Reason]`: `has_field`, `date_in_future`, `image_or_exception`, `four_eyes` (stub) |
| `snapshot.py` | `Snapshot`/`Actor` built from rows; a guard never touches DB or session |
| `reasons.py` | `Reason {code, field, severity, messageKey, fixAction}`, `blocker`, `blockers` |
| `service.py` | `PipelineService.guards` and `stage_fire`: decide, `UPDATE ... WHERE state = :from AND rev = :rev`, revision, status event, audit; never commits |
| `actions.py` | post-commit actions keyed `event:<id>:rev:<n>:<action>` (Redis SET NX): `ensure_derivatives`, `invalidate_feed_cache` |
| `slugs.py` | T04 slug `<YYYY-MM-DD>-<title-slug>`, `-2` on collision |
| `exception.py` | `image_exception` for one event id (editor, reason >= 10 chars, audited) |
| `router.py` | `POST /transitions/{T}`, `GET /guards/{T}`, `POST /image-exception`; commits, then runs actions |
| `0002_events_core.py` | `enforce_publish_image`, `keep_published_poster`, `append_only_guard` |

## Data model

| Id | From to | Permission | Guards in order | Sets / actions |
|---|---|---|---|---|
| T00 | new to `idea` (events service) | `event.create` in target org | org in scope (404 outside) | revision 1, audit |
| T01 | `idea` to `planning` | `event.edit`, submitter own only | `has_field(title, starts_at, organization_id)` | |
| T02 | `planning` to `in_review` | `event.submit` | `has_field(+summary, ends_at, primary_category_id, venue_text)`, `date_in_future` | `submitted_by` |
| T04 | `in_review` to `approved` | `event.approve` (editor, trusted approver) | `date_in_future`, `image_or_exception`, `four_eyes` | `slug`, `public_seq`, `approved_by`; `ensure_derivatives` |
| T05 | `approved` to `live` | `event.approve` | `date_in_future`, `image_or_exception` | `invalidate_feed_cache` |

Every fire writes `event_revision` (new `rev`), `event_status_event` and `audit_entry` in one transaction.

## API

`POST /api/events/{id}/transitions/{T}` with `{note?}` (<= 500): 200 `Event`; 422 with `code` = first blocker and
`reasons[]`; 409 `invalid_transition` or `conflict`; 403 when visible but the right is missing; 404 when not visible.
`GET /api/events/{id}/guards/{T}`: `{transition, allowed, reasons[]}`, computed and never stored; `allowed` needs
right, state and guards. `fixAction` is `fill_field | change_date | upload_poster | null`, `messageKey` is
`guards.<code>` (the frontend translates).

## Gotchas

- `stage_fire` is the only writer of `event.state`. Never add another; PATCH cannot touch it.
- `decide` order: right (`forbidden`), then state (`invalid_transition`), then guards (`blocked`).
- `date_in_future` checks `ends_at > now`, so a running event passes; the code is still `start_in_past`.
- `image_required` holds only with a poster `scan_status = clean`, derivatives, alt text, credit and
  `rights_basis != unknown`, or a valid `image_exception`. Without the worker the poster never qualifies.
- Second layer: trigger `enforce_publish_image` on `INSERT OR UPDATE OF state, hero_attachment_id, image_exception`
  for `approved` and `live`, SQLSTATE `23514`; `keep_published_poster` stops a published poster from losing `clean`
  or being retired. `stage_fire` maps a 23514 from the trigger to the `image_required` refusal.
- `four_eyes` is wired into T04 but always holds in M1; `EDITOR_FOUR_EYES` is not read yet (M3).
- `invalidate_feed_cache` only bumps Redis `events:feed:version`; the feed reads the view per request in M1.
- PATCH: `idea`/`planning` all fields for org roles; `in_review` and later 409 `field_locked`. Poster upload in
  `in_review` only for approver/editor, from `approved` on 409 `field_locked`.
- Audit for derive is `attachment_scan` with `status: derived` (the action catalog stays as copied).

**Tests:** `tests/unit/pipeline/{test_transitions_matrix,test_guards,test_service_write,test_slugs_actions}.py`,
`test_publish_property.py` (hypothesis state machine: no sequence reaches `live` without poster or exception),
`tests/integration/events/test_rbac_matrix.py` (full role x transition matrix), `test_db_nets.py`
(`test_direct_sql_publish_rejected`, insert in a published state), `tests/integration/test_audit_chain.py`.
End to end: `backend/scripts/m1_acceptance.py`, `frontend/e2e/m1.spec.ts`.

**Siblings:** `be-events`, `be-auth`.
