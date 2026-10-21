---
name: be-lifecycle
description: The lifecycle of a dossier in STUPA Events since M5b. Three states (draft, published, archived) plus the public status flag (cancelled, postponed), one route per action (publish, unpublish, archive, restore, cancel, postpone, reinstate, revert-revision), allowedActions, editable fields per state, missing_info hints instead of guards, publish_requires_editor, post-commit actions, the worker archive_ended and optimistic locking. Use when working on who may publish, state changes, hints, public status or the worker that archives.
---

# Lifecycle: `backend/app/modules/events/{lifecycle,step,publish,allowed,editing,hints,public_status,revert}.py`, `backend/worker/advance.py`

**Does:** Moves a dossier between `draft`, `published` and `archived` and changes the public status (`scheduled`,
`cancelled`, `postponed`) of a published one. There is no approval, no Four-Eyes, no field classes and no guard
system; the pipeline belongs to the Workflow tool. Contract: `docs/M5B-KONTRAKT.md` (on top of M1 to M5).

## Key files

| File | Role |
|---|---|
| `states.py`, `models.py` | `EventState` (three values); `LEGACY_STATES` only for the history CHECK on `event_status_event` |
| `lifecycle.py` | `publish`, `unpublish`, `archive`, `restore`, `archive_as_system` (worker); `EDITOR_RIGHT = event.restore` |
| `step.py` | `prepare` (404 without read right, 409 `conflict` on a stale `rev`, 403 without the right in the dossier's org) and `finish` (optimistic `UPDATE`, revision, status event with the action word as `transition_id`, audit); never commits |
| `publish.py` | the only hard rule: title, start, organization, else 422 `publish_incomplete` with `reasons[]` |
| `public_status.py` | `cancel`, `postpone`, `reinstate` on `published` (`event.cancel`), `public_seq + 1`, feed invalidation |
| `allowed.py` | `allowed_actions` for `EventOut.allowedActions` (a hint; the server decides on a write) |
| `editing.py` | `may_edit`, `editable_fields` (all or none), `PUBLIC_FIELDS`, `bumps_public_seq` |
| `hints.py`, `hints_data.py` | pure `missing_info(HintInput) -> list[Hint]` and its loader; `GET /api/events/{id}/hints` |
| `postcommit.py`, `slugs.py`, `revert.py`, `notices.py`, `respond.py` | Redis-claimed post-commit actions (`ensure_derivatives`, `invalidate_feed_cache`), slugs, revert through the PATCH derivations, `published`/`cancelled` notices |
| `lifecycle_router.py` | `POST /api/events/{id}/{publish,unpublish,archive,restore,cancel,postpone,reinstate}` and `/actions/revert-revision` |
| `worker/advance.py` | `archive_ended` (every 15 min): published and ended 12 h ago, cancelled ones too, batches of 200, one session per dossier; `purge_drafts` |

## Rules

- `publish` draft to published (`event.publish` in the org; with `PUBLISH_REQUIRES_EDITOR=true` only the editorial
  team), sets the slug when empty, `public_seq + 1`. `unpublish` back to draft (slug stays). `archive` from draft or
  published (`event.publish`; the worker as `actor_type = system`). `restore` archived to draft (`event.restore`,
  editorial team only).
- Base data: `draft` with `event.edit` (a submitter only on its own), `published` with `event.publish`, `archived`
  locked (409) until `restore`. The documentation (documents, attachments, checklist, comments, quotes, outcome,
  verify-howto) stays writable in the archive (contract 2.4).
- No image is needed; a missing poster is the hint `no_poster` (`warn` when published) and the feed says `image: null`.
- Every action needs `If-Match` (428 without, 409 `conflict` with `current` on a stale one) and answers `EventOut` with
  the new ETag. Wrong state is 409 `invalid_state`.
- Status events and revisions are append-only; old rows keep the eight pre-M5b state names as text.

**Tests:** `tests/unit/events/{test_lifecycle_matrix,test_hints,test_publish_incomplete,test_slugs_postcommit}.py`,
`tests/integration/events/{test_flow,test_actions,test_rbac_matrix,test_locking_and_fields,test_db_nets}.py`,
`tests/integration/archive/test_followup.py` (worker `archive_ended`), `tests/integration/test_migration_0007.py`.
Acceptance: `scripts/m5b_acceptance.py` (`m5b_dossier.py`, `m5b_rights.py`).

**Siblings:** `be-events`, `be-auth`, `be-archive`.
