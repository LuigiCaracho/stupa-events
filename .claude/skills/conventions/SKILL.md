---
name: conventions
description: STUPA Events house rules, Definition of Done, test and coverage gates, Alembic policy and the shared backend utilities (problem+json, permissions, guards). Read this FIRST before changing backend or frontend code, opening a PR or writing a migration. Use when unsure how this repo expects code, errors, types, i18n or migrations to be done.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/conventions/SKILL.md (adapted). -->
# Project conventions: house rules and Definition of Done

Source of truth: `CONTRIBUTING.md`, `.github/pull_request_template.md`, `docs/M1-KONTRAKT.md`. Rules are
inherited from STUPA-Workflow@93c33d6; each encodes a bug that already cost time there.

## Workflow

- TDD: red, green, refactor. No `skip`/`xfail` without a linked issue.
- Feature branch per task, squash PR into `development`. No push and no deploy without the owner's okay.
- Ask before design decisions that the plan or the contract does not settle.

## Backend rules

- **tz-aware everywhere**: `timestamptz` in the DB, aware `datetime` in Python (`datetime.now(UTC)`, never `utcnow()`).
  Naive input is a 422.
- **problem+json on all error paths** (`app/shared/errors.py`): `{type, title, status, code, detail?, errors?, traceId?}`.
  Guard refusals add `extensions` (`reasons[]`).
- **RBAC server-side**: `Principal.has(perm, org_id=...)` decides, never `principal.roles`. Org comes from the group
  name, never from body or query. No read right means 404, not 403 (no existence oracle).
- **Strict types**: Pydantic v2 camelCase base model with `extra="forbid"`, `Literal`/enums instead of free strings.
- **No `eval`** (`test_no_eval`). Python 3.13 typing: `list[str]`, `X | None`, fully annotated.
- **One writer for state**: only `PipelineService.fire` changes `event.state`. The router commits.
- Google-style docstring in every file, function and class; no divider comments; small files.

## Frontend rules

- Angular 20 standalone, OnPush, signals, strict TS, separate `.html`/`.scss`. UI strings are German i18n keys
  (colon or neutral gender); `en` parity from stage B.
- Same field names as the API, camelCase. Types for the API client are written by hand from the contract.
- Check both themes against the production build; run `npm run build` after CSS changes.

## Gates

Backend: `ruff`, `basedpyright` 0 errors, unit and integration suites, coverage 90 % overall in M1 (97 % by M5),
100 % branch for `pipeline` and `publicapi`. Frontend: `eslint`, `tsc`, jest thresholds, production build.
CI jobs: `be-lint`, `be-typecheck`, `be-unit`, `be-integration`, `migrations-check`, `fe-unit`, `compose`, `gitleaks`.

## Migrations

`uv run alembic revision -m "..."`; `alembic heads` shows one head; revision id at most 32 characters;
`alembic upgrade head` runs green on a fresh DB. M1 ids: `0001_baseline`, `0002_events_core`. Additive only
(expand/contract). DB roles: `deploy/db/roles.sql` before and after the migration.

## Copied files

Header `Copied from STUPA-Workflow@93c33d6 <path>` and a `PROVENANCE.json` entry (`K` unchanged, `U` adapted).
`test_provenance` keeps them in sync; the weekly `upstream-drift` workflow reports upstream changes as an issue.
