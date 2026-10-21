---
name: be-pipeline
description: The event state machine of STUPA Events (M3). 14 transitions T01 to T12 as data, guards as pure functions with ordered reasons[], decide(), Four-Eyes, field classes, actions (cancel, postpone, reinstate, assign, revert), the advance_states worker, optimistic locking, post-commit actions and the DB nets. Use when working on transitions, guards, who may publish, field locks, public status or the worker that moves dossiers on.
---

# Pipeline: `backend/app/modules/pipeline`, `backend/worker/advance.py`

**Does:** Moves a dossier through `idea`, `planning`, `in_review`, `approved`, `live`, `followup`, `archived` and
`withdrawn` by 14 transitions, and changes the public status (`scheduled`, `cancelled`, `postponed`) of a live
dossier by actions. Contract: `docs/M3-KONTRAKT.md` (on top of M1 and M2).

## Key files

| File | Role |
|---|---|
| `transitions.py` | `TRANSITIONS`: id, sources, target, permission, guards in table order, `note_required`, `four_eyes`, `system`, `sets` (column, rule), `actions` |
| `decision.py` | pure `decide(transition, snapshot, actor, now, note_given)`: right, state, note, Four-Eyes, guards; `allowed_transitions` |
| `guards/` | `fields`, `media`, `content`, `timing`: every guard `(snapshot, actor, now) -> list[Reason]` |
| `snapshot.py`, `actor.py` | `Snapshot`, `PosterSnapshot`, `Actor(kind, four_eyes)`, `SYSTEM_ACTOR`; `actor_of(principal, org_id)` |
| `service.py` | `PipelineService.guards`, `stage_fire` (people), `stage_system_fire` (worker): one `_fire`, optimistic `UPDATE`, revision, status event, audit; never commits |
| `values.py` | the columns a transition writes (rules `actor`, `null`, `plus_one`, `new_rev`, `body`, `slug`, `scheduled`) |
| `fieldclass.py` | pure `plan_patch`, `edit_right`, `editable_fields`, `lock_reason`, `link_hosts` |
| `livecheck.py` | the guards that run again on the result of a critical change in `live` |
| `actions_service.py` | `cancel`, `postpone`, `reinstate`; `assign.py`, `revert.py`, `marks.py` (`acknowledge_changes`, `confirm_flyer`), `exception.py` (image exception); shared steps in `action_base.py` |
| `advance.py` | pure `due_transition(AdvanceRow, now)`; the run is `worker/advance.py` |
| `actions.py` | post-commit actions `event:<id>:rev:<n>:<action>` (Redis SET NX): `ensure_derivatives`, `invalidate_feed_cache` |
| `router.py`, `actions_router.py` | `POST /transitions/{T}`, `GET /guards/{T}`, `POST /actions/{name}`, alias `POST /image-exception` |

## Transitions

T01 idea to planning; T02 planning to in_review (`submitted_by`); T03 back to planning (note); T04 to approved
(Four-Eyes, `slug`, `public_seq + 1`, optional `publishAt`); T05 to live; T06 approved back to in_review (note);
T07 live to approved (note, `public_seq + 1`, public status reset); T08 live to followup (worker, ended 12 h,
origin internal or mcp); T08b live to archived (worker, imported or legacy); T09 followup to archived; T09b the
worker after 30 days; T10 archived to followup (editor, note); T11 withdraw (note; the proposer too); T12 restore
(editor). Note mandatory: T03, T06, T07, T10, T11 (`reason_required`).

## Gotchas

- `stage_fire` and `stage_system_fire` are the only writers of `event.state`; PATCH never touches it.
- `decide` order: right (403), state (409 `invalid_transition`), note (422), Four-Eyes (403 `four_eyes`), guards
  (422 with the code of the first blocker, `reasons[]` in table order, warnings never block).
- Four-Eyes binds org approvers and admins always, editors only with `EDITOR_FOUR_EYES`; the same rule is a CHECK on
  `event_status_event` (`ck_event_status_event_four_eyes`), the service maps 23514 to the same 403.
- `date_in_future`, `publish_at_reached` and `human_approval` bind the worker only (humans may publish early).
- The worker has no side door: `stage_system_fire` calls `decide` with `SYSTEM_ACTOR`; a poster that turned invalid
  gives `blocked`, the trigger `enforce_publish_image` is the second net.
- Real guards since M5: `locationConfirmed`, `factsValid`, the four of T09 (`checklistDone(followup)`,
  `retrospectiveFilled`, `outcomeSetOrWaived`, `howtoVerified`). Still neutral: duplicates (M6) and the wall-clock
  warnings (M6). `Transition.checklist_phase` names the phase a checklist guard reads (`planning`, T09 `followup`).
- T09 by a person sets `format.last_verified_at/_by` and verifies the master howto in the same transaction
  (`formats/verification.py`); T09b never touches the format and sends `auto_archived` (`pipeline/notices.py`).
- T08, T08b, T09, T09b and T10 carry `invalidate_feed_cache`, which bumps `events:feed:version` and queues
  `rebuild_public_cache` (`pipeline/actions.py`, `request_rebuild`).
- Version: `If-Match` (or body `rev`) against `event.rev`; a stale one is 409 `conflict` with `current`; a missing
  one on PATCH/PUT draft is 428.
- Reasons of cancel/postpone/reinstate live in `event_status_event.note` only (never audit, revision, feed).
- `public_seq` moves in T04, T07, the status actions and live changes of critical fields or the summary.
- `If-Match` is mandatory (428) for T04, T05, cancel, postpone, reinstate and revert-revision (`require_if_match`); the
  harness `api.fire`/`api.action` adds it, `without_if_match=True` tests the 428. `revert-revision` runs `plan_patch` and
  refuses `plan.locked` like `PATCH`; every new write path to content fields must do the same.
- `tests/unit/pipeline/oracle.py` is an independent table; keep it free of imports from `transitions`.
- Cards (`events/cards.py`) build the same full snapshot as `GET /guards` through `events/card_extras.py`; a new
  guard input that needs a query goes into both `access.guard_snapshot` and `card_extras`.
- Every arq worker on the queue `events` takes jobs: an old worker process left running (M2 code) answers
  `function 'advance_states' not found` for a share of the jobs. Before a worker check `pgrep -af 'arq worker'`
  must show only the `stupa-worker` unit.

**M4 data behind the guards:** `dossier/guard_data.py` fills `open_comments` (T03 needs one), `open_hero_comments` (anchor `hero`
or any file in the poster's replacement chain, T04), `open_required_checklist` (planning, T02), `quarantined_attachments`
(poster, social post or shared file, hero excluded) and the flyer check (`contains_date`/`dated_for`, same file in another
year). `rightsComplete` reports one reason per open field (`altText`, `credit`, `rightsBasis`, `consentNote`);
`imageOrException` only checks scan and derivatives. `pipeline/notices.py` creates the notifications of a transition or
action; the routers send the returned mails after the commit.

**Tests:** `tests/unit/pipeline/*` (full matrix against the oracle, guards, U-GUARD, field classes, actor, advance,
property), `tests/integration/pipeline/*` (full flow, Four-Eyes, worker, U-GUARD with DB, `test_api_walk.py`: seeded random walks over the real API with the publish invariants; extend its operations when a new write path appears), `tests/integration/events/
{test_rbac_transitions,test_actions,test_field_classes_api,test_autosave}.py`. Acceptance: `scripts/m3_acceptance.py`.

**Siblings:** `be-events`, `be-auth`.
