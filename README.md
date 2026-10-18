# STUPA Events

Event pipeline with dossiers, roles and a PWA for the student parliament (StuPa) of Hochschule
Reutlingen. Fachschaften and initiatives plan events as dossiers, the editorial team approves them,
and approved events with a poster appear in a public feed for the website.

Status: milestone M1 (walking skeleton). The specification is `PLAN.md` in the separate planning
directory `stupa-events-plan`; the contract for M1 is [`docs/M1-KONTRAKT.md`](docs/M1-KONTRAKT.md).
The platform reuses the proven scaffold of STUPA-Workflow (files marked `Copied from
STUPA-Workflow@93c33d6`, listed in `PROVENANCE.json`).

## Stack

Backend: Python 3.13, FastAPI, SQLAlchemy 2 async, Alembic, arq. Frontend: Angular 20 with the
`@stupa-makers/ui-kit` submodule. Data: Postgres 16, Redis 7, MinIO, ClamAV. One VM, `docker
compose`, plain HTTP inside, TLS at an external Caddy.

## Development

Needs Docker, [Nix](https://nixos.org) (or Python 3.13 + uv, Node 24) and, for the dev IdP, one
`/etc/hosts` line: `127.0.0.1 host.docker.internal`.

```bash
git submodule update --init --recursive
cp deploy/.env.dev.example deploy/.env.dev

# Option A: whole stack in containers (web 8081, postgres 5434, Keycloak 8090)
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.keycloak.yml \
  --env-file deploy/.env.dev up -d --build
deploy/smoke.sh

# Option B: backing services only, backend and frontend on the host (no /etc/hosts line needed)
docker compose -f deploy/docker-compose.dev.yml up -d
cp deploy/.env.host.example backend/.env
docker exec stupa-events-dev-postgres-1 psql -U postgres -d events -f /db/roles.sql   # after each migration
nix develop .#backend  -c bash -c 'cd backend && uv sync && uv run alembic upgrade head && uv run python -m scripts.seed_dev'
nix develop .#backend  -c bash -c 'cd backend && uv run --env-file .env uvicorn app.main:app --port 8000'
nix develop .#backend  -c bash -c 'cd backend && uv run --env-file .env arq worker.main.WorkerSettings'
nix develop .#frontend -c bash -c 'cd frontend && npm ci && npm start'   # http://localhost:4200
```

The worker is needed for posters (ClamAV scan, WebP derivatives) and moves dossiers on: `advance_states` every quarter
hour (scheduled publication `approved` to `live`, `live` to `followup`/`archived` 12 h after the end, `followup` to
`archived` after 30 days) and `purge_drafts` daily at 03:30 UTC (autosave drafts older than 14 days).
A `T05` without `publishAt` always waits for a person.
`backend/scripts/m1_acceptance.py`, `m2_acceptance.py` and `m3_acceptance.py` walk the criteria of M1 to M3 against this
setup (see `docs/M1-ABNAHME.md`, `docs/M2-ABNAHME.md`, `docs/M3-ABNAHME.md`). `m3_acceptance` waits for one worker run.

The roles in `deploy/db/roles.sql` are created on the first Postgres start; after migrations run
`psql -U postgres -d events -f /db/roles.sql` once more for stage 2 (the grants that need the tables).

Run `python -m scripts.seed_dev` once after the migrations: it maps the realm groups in `group_mapping`
(a group name grants nothing without a row) and loads the reference data and nine dossiers in every stage up to the archive, one of them a proposal.

Test users (password `password`, local Keycloak only), all in `events-users`: `admin` (events-admin), `editor`
(events-editor), `stupa` (events-stupa), `approver-stupa` and `approver2-stupa` (events-stupa-approver, trusted; the second person approves what the first
submitted, Four-Eyes), `approver-fsi`
(events-fsi-approver, acts as organizer), `organizer-fsi`, `submitter-fsi`, `viewer-fsi`, `organizer-makers`,
`submitter-ekhg` (partner account) and `member` (no role group). A running Keycloak gets the new users with
`python -m scripts.m2_acceptance` (it syncs the realm file first). Instead of Keycloak you can use Luis' Authentik, see
[`docs/authentik/README.md`](docs/authentik/README.md).

## Tests

| What | Command |
|---|---|
| Backend lint, types | `cd backend && uv run ruff check . && uv run ruff format --check . && uv run basedpyright` |
| Backend unit | `cd backend && uv run pytest -m 'not integration and not e2e and not live'` |
| Backend integration (Docker) | `cd backend && uv run pytest -m integration` |
| Migrations | `cd backend && uv run alembic heads && uv run alembic upgrade head` |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npm test && npm run build` |
| Compose | `deploy/compose-lint.sh` and, with the stack up, `deploy/smoke.sh` |
| E2E | `cd frontend && npx playwright test` (browsers via `nix build nixpkgs#playwright-driver.browsers`) |
| Secrets | `gitleaks detect` |

## Operations

`deploy/backup.sh` (pg_dump through age, MinIO mirror without derivatives, manifest) and
`deploy/restore-smoke.sh` (restores the newest backup into a throwaway Postgres and compares row counts)
work against the local stack. `deploy/deploy.sh vX.Y.Z` is the production update (tag checkout, build
under flock, recreate changed services); it is documented and has never been run.

Both ran once locally (`docs/M1-ABNAHME.md`); `backup.sh` takes `COMPOSE_FILE` and `ENV_FILE`, so it also
works against the dev services. Open for M1 on a real server: measure VM RAM next to the Workflow stack
(local idle figure in `docs/M1-ABNAHME.md`), decide on the ClamAV container (E23), and run backup plus
restore once on the VM.

## Layout

```
backend/    FastAPI app, worker, migrations, tests
frontend/   Angular app, ui-kit submodule in frontend/vendor/ui-kit
deploy/     compose files, nginx, DB roles, scripts, dev IdP realm
docs/       M1 contract, Authentik blueprint
.github/    CI, upstream-drift, PR template
```
