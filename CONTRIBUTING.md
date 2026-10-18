<!-- Copied from STUPA-Workflow@93c33d6 CONTRIBUTING.md (adapted for STUPA Events). -->
# Contributing — STUPA Events

Binding workflow: **TDD (Red-Green-Refactor)**. The CI gate blocks pull requests
(`.github/workflows/ci.yml`). This document collects the workflow, the Definition of Done and the
branch protection settings.

## TDD: Red → Green → Refactor

1. **Red** — Write the test first. It describes the wanted behavior. Run it. It *must
   fail*. A test that fails before the production code exists is a real test.
2. **Green** — Write the smallest amount of production code that makes the test pass.
   Write no more.
3. **Refactor** — Remove duplication and clutter. The tests stay green.

Do not use `skip` or `xfail` without a stated reason and a link to an issue.

## Local tests

Backend (`backend/`, shell: `nix develop .#backend`):

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright                                   # 0 errors required
uv run pytest -m 'not integration and not e2e and not live'
uv run pytest -m integration                          # testcontainers, Docker required
uv run alembic heads                                  # exactly one head
```

Frontend (`frontend/`, shell: `nix develop .#frontend`; needs the ui-kit submodule):

```bash
git submodule update --init --recursive
npm ci
npm run lint && npm run typecheck
npm test -- --coverage --watch=false
npm run build                                         # production build, run it after CSS changes
npx playwright test                                   # E2E against the compose stack
```

Stack and dev IdP: see `README.md`. Secrets: `gitleaks detect` before every push.

## Coverage gates (CI fails below the limit)

- Backend: 90 % overall in M1 (`[tool.coverage.report] fail_under`), rising to 97 % by M5.
  `pipeline` and `publicapi` need 100 % branch from M1.
- Frontend: jest `coverageThreshold` from `frontend/jest.config`.

## CI stages (`.github/workflows/ci.yml`)

The jobs start in parallel. Required for `main`: `be-lint`, `be-typecheck`, `be-unit`,
`be-integration`, `migrations-check`, `fe-unit`, `compose`, `gitleaks`. `compose-smoke` builds
the whole stack and is opt-in (label `run-compose-smoke`, manual run, or a push to `main`).
The weekly `upstream-drift` workflow only opens an issue.

## Definition of Done (per task or module)

The checklist in the pull request template (`.github/pull_request_template.md`) is
binding. It asks in advance about our recurring review errors. Each item stands for an
error that already cost us at least once. The same items follow as prose. Each one
carries a short *why*:

- **tz-aware (timestamptz, no mix of naive and aware).** Use `timestamptz` for every
  timestamp in the database and an aware `datetime` in Python (`datetime.now(UTC)`,
  never `utcnow()`). *Why:* a naive value from a migration or a seed already crashed
  RBAC (`can't compare offset-naive and offset-aware`). That fault then caused a
  meeting WebSocket 403. A single naive value poisons every comparison.
- **problem+json on ALL error paths.** Every 4xx and 5xx returns
  `application/problem+json`. This also holds for a branch you add later. *Why:* the
  contract tests and the frontend expect one error schema. A bare string
  or the FastAPI default `detail` breaks both. A local visual check misses it easily.
- **RBAC enforced on the server, no privilege escalation.** The backend checks the
  permission. Frontend gating alone is not enough. Roles and owner come from the
  session, never from the request body. *Why:* frontend gating gives comfort, not
  security. A caller that hits the route directly goes around it. An object owner that
  differs from the caller is the most frequent leak.
- **Same names in the frontend and backend contract.** Use the same field, header and
  cookie names on both sides. Use **camelCase** in JSON. *Why:* drift between
  `snake_case` and `camelCase` comes back again and again. So do frontend fields that
  the backend never had. Both sides compile and then fail silently at run time.
- **Strictly typed inputs (enums and literals instead of free strings).** Validate
  query, body and path through Pydantic and `Annotated`. Model a status field as an enum
  or a `Literal`. *Why:* an open `str` status field accepts typos and invalid
  transitions. The error then breaks out deep in the code. The `lang` parameter was such
  a case. It was free text instead of `de|en`.
- **i18n.** Add every new string as a `de` key. Hard-code nothing. Gender with a colon
  (Teilnehmer:innen) or word it neutrally. English parity follows in stage B. *Why:* a
  hard-coded string never reaches the translation catalog.
- **a11y.** Labels and `aria-*`, focus order, keyboard, contrast.
- **Dark and light.** Check both themes. *Why:* fixed colors break in the other theme
  again and again. The production build (inlineCritical) also behaves differently from
  the dev build. Check against the **production** build.
- **Frontend self-check (before and after).** Take Playwright screenshots and *look* at them, one set per theme.
  *Why:* "it probably looks fine" is
  not a self-check. Most layout regressions show up only in the screenshot.
- **Single migration head.** `alembic heads` shows one head. `alembic upgrade head` runs
  green. See "Database migrations (Alembic)" below.

Plus the hard gates:

- Tests written first, all green.
- Coverage gate held (M1: 90 % overall, 100 % branch for `pipeline` and `publicapi`).
- `ruff` and `basedpyright` (BE), `eslint` and `tsc` (FE) green.
- Contract tests green (`test_camel_case_contract`, `test_route_authz_inventory`, `test_rbac_matrix`), affected E2E tests green.
- No `skip` or `xfail` without a linked reason.

## Copied files

Every file taken from STUPA-Workflow starts with `Copied from STUPA-Workflow@93c33d6 <path>`
in its header docstring and has an entry in `PROVENANCE.json` (mode `K` = copied unchanged,
`U` = copied and adapted). `test_provenance` keeps both in sync.

## Database migrations (Alembic)

```bash
cd backend
uv run alembic revision -m "short_description"
uv run alembic heads            # MUST show exactly one head
uv run alembic upgrade head     # MUST run green on a fresh database
```

- The revision id has at most 32 characters (`alembic_version varchar(32)`). `0001_baseline` and
  `0002_events_core` are the M1 revisions; later ones may use Alembic's hash ids.
- `down_revision` points to the **current** head.
- Migrations are additive (expand/contract). A destructive step needs its own release.
- The roles in `deploy/db/roles.sql` run before (stage 1) and after (stage 2) `upgrade head`.
  `test_db_grants` guards the result.

## Branch protection (`main`)

Branch model: `main` protected, `development`, `feat/*` and `fix/*` merged by squash PR, tags
`vMAJOR.MINOR.PATCH` (annotated). Under **Settings → Branches**:

- Require a pull request before merging (at least 1 review).
- Require status checks (see CI stages) and an up-to-date branch.
- Require conversation resolution; no bypass for admins; no force push, no branch deletion.

No push and no deploy without the owner's okay. `deploy/deploy.sh` checks out a tag; nothing
else deploys.
