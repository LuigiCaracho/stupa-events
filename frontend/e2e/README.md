# E2E (Playwright)

`m1.spec.ts` is the M1 acceptance run: organizer-fsi creates a dossier, uploads a poster and asks for approval,
editor approves and publishes, the event shows in `/api/public/feed/events`, and an approval without poster
returns 422 `image_required`.

`m2.spec.ts` is the M2 acceptance run: editor adds a category (no mapping tab), admin adds and removes a group
mapping and is refused a reserved `events-system:` group, organizer-fsi gets not found for a foreign dossier, and
"Andere Sitzungen widerrufen" ends only the other session.
It needs the M2 dev users (`admin`, from `deploy/keycloak/stupa-events-realm.json`) in the running Keycloak.

`m3.spec.ts` is the M3 acceptance run: keyboard drag on the board and the phone tabs, four-eyes (needs the dev user
`approver2-stupa`), the field classes in `live`, a cancellation that stays in the feed as `cancelled`, autosave across a reload
with the edit conflict, a proposal of a `member`, and axe in light and dark (`support/axe.ts`, `@axe-core/playwright`
4.13.0). Run it against the compose `web` container (production build) for the axe gate.

`m4.spec.ts` is the M4 acceptance run: a question on the poster blocks the approval in the guard list until it is resolved, the
checklist with its template, a mail template with live preview and the sentence for an unknown placeholder, a foreign
organization (`organizer-makers`) getting 404 on the quotes and tabs of an FSI dossier, and axe on the new tabs.
It needs the M4 backend (migration `0005`) in the running stack.

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
