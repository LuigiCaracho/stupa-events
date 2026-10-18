<!-- Copied from STUPA-Workflow@93c33d6 CLAUDE.md (adapted). -->
# CLAUDE.md: agent guide to STUPA Events

Entry point for any AI agent working in this repo. Skills are per-area navigation docs under
`.claude/skills/<name>/SKILL.md`. Read `conventions` first.

## What this is

**STUPA Events** is an event pipeline with dossiers, roles and a PWA for the student parliament of
Hochschule Reutlingen. A dossier (event) moves idea, planning, in review, approved, live; the guard
`image_required` blocks publishing without a poster (checked in the API and by a DB trigger). Live
events appear in the public feed `GET /api/public/feed/events` (schema 2) for the website.

It is a second, fully separate stack beside the Workflow tool (STUPA-Workflow). Files copied from there
carry `Copied from STUPA-Workflow@93c33d6 <path>` and an entry in `PROVENANCE.json`. The binding
specification lives outside the repo (`stupa-events-plan/PLAN.md`); the contract of the current
milestone is `docs/M3-KONTRAKT.md` (on top of `docs/M2-KONTRAKT.md` and `docs/M1-KONTRAKT.md`, which still hold).

**Stack:** Python 3.13, FastAPI, Pydantic v2 (camelCase, `extra=forbid`), SQLAlchemy 2 async,
Alembic, arq worker. Angular 20 (standalone, OnPush, signals, strict TS, separate `.html`/`.scss`),
`@stupa-makers/ui-kit` submodule. Postgres 16, Redis, MinIO, ClamAV. Compose project `stupa-events`
(web 8081, postgres 5434), dev IdP Keycloak 8090.

## Skills

- **conventions**: house rules, Definition of Done, gates, migration policy. **Start here.**
- **be-auth**: OIDC with PKCE, sessions, groups to roles, `/auth/me`
- **be-events**: event model, organizations, categories, poster, public feed, `public_event_v`
- **be-pipeline**: state machine T01 to T12, guards, Four-Eyes, field classes, actions, worker, optimistic locking
- **frontend**: Angular app, shell, features, i18n, tests
- **deploy**: compose stack, nginx and CSP, DB roles, backup, CI, dev IdP

## Commands

- Backend (`backend/`): `uv run ruff check .` · `uv run basedpyright` · `uv run pytest -m 'not integration and not e2e and not live'` · `uv run pytest -m integration`
- Frontend (`frontend/`): `npm run lint` · `npm run typecheck` · `npm test` · `npm run build`
- Migrations (`backend/`): `uv run alembic heads` (one head) · `uv run alembic upgrade head`
- Stack: `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.keycloak.yml --env-file deploy/.env.dev up -d --build`, then `deploy/smoke.sh`
- Lint the stack: `deploy/compose-lint.sh`

## Rules that bite

- Never touch live systems (stupa.reutlingen.university, workflow.*, sso.*). Local Docker only.
- No push and no deploy without the owner's okay. `deploy/deploy.sh` is documentation until then.
- Code, docstrings, commits in English; UI strings German, gendered with a colon or neutral.
