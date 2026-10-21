# E2E (Playwright)

`m1.spec.ts` is the M1 run, cut down by M5b: organizer-fsi signs in (role from the group), creates a dossier, drops a poster and publishes it; the event is in
`/api/public/feed/events` with its image; a viewer cannot publish (403, no button); the editor publishes a draft without a poster (`image: null`).

`m2.spec.ts` is the M2 run: editor adds a category (no mapping tab), admin adds and removes a group mapping and is refused a reserved
`events-system:` group, organizer-fsi gets not found for a foreign dossier, and "Andere Sitzungen widerrufen" ends only the other session.
It needs the M2 dev users (`admin`, from `deploy/keycloak/stupa-events-realm.json`) in the running Keycloak.

`m3.spec.ts`: the dossier page edits like one form in every state (no field classes), autosave across a reload with the edit conflict, the
archive locks the key data until the editor restores, the anchor navigation on the phone, a member without an organization gets the note, axe.

`m4.spec.ts`: a question on the poster is a thread and never blocks publishing, the checklist with its template, a mail template with live preview and the
sentence for an unknown placeholder, a foreign organization (`organizer-makers`) getting 404, attachments and howto, the sections at 360 px, axe.

`m5.spec.ts`: a new edition from an archived Movienight (preview, no poster, "Letztes Mal"), "Fachschaftssitzung" finds "Sitzung", the palette (Strg+K), the
calendar by keyboard inside the event list, "So lief es" written in the archive, archive, formats and library at desktop width and 360 px with axe.

`m5b.spec.ts` is the M5b acceptance: draft, howto, poster by drop, publish (feed with image); a second event without a poster (banner, feed `image: null`);
an archived event as the template of a new draft with the copied howto; cancel stays in the feed as `cancelled`, unpublish removes the event, the editor restores;
the dossier page, the list and the calendar through axe at 1280 px and 360 px. It needs the M5b backend (migration `0007`).

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
