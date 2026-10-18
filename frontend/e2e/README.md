# E2E (Playwright)

`m1.spec.ts` is the M1 acceptance run: organizer-fsi creates a dossier, uploads a poster and asks for approval,
editor approves and publishes, the event shows in `/api/public/feed/events`, and an approval without poster
returns 422 `image_required`.

Needs the compose stack with the Keycloak overlay and `127.0.0.1 host.docker.internal` in `/etc/hosts`
(see `docs/M1-KONTRAKT.md` sections 1 and 8). The tests open `http://localhost:8081` (the registered
redirect URI); override with `E2E_BASE_URL`. Run `npx playwright test` in `frontend/`.

Without the full stack (no `/etc/hosts` change needed): run the dev services
(`docker compose -f deploy/docker-compose.dev.yml up -d`), the API and the worker on the host with
`backend/.env` from `deploy/.env.host.example` (`uv run --env-file .env uvicorn app.main:app --port 8000` and
`uv run --env-file .env arq worker.main.WorkerSettings`), `npx ng serve` on 4200, then:

```bash
export PLAYWRIGHT_BROWSERS_PATH=$(nix build --no-link --print-out-paths nixpkgs#playwright-driver.browsers)
PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m1.spec.ts
```

`@playwright/test` is pinned to the nixpkgs driver version (1.63.0); bump both together.
