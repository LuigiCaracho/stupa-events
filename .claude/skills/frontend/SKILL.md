---
name: frontend
description: Angular 20 app of STUPA Events (frontend/). Shell, auth, i18n, theme, PWA update, the ui-kit submodule, the M1 feature pages (tasks, new event, dossier head with poster, guard list and transition buttons), the M2 admin area (taxonomy, group mappings, session revoke) and the build and test gates. Use when working on any file under frontend/, on routing, translations or the API client types.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/frontend/SKILL.md (adapted). -->
# Frontend: `frontend/`

**Does:** Single-page PWA. The shell (`core/`, `shared/ui`) owns routing with frames `rail`, `public`, `bare`,
`pending`, auth state, i18n (de), theme and the service-worker update prompt. Features live in
`src/app/features/**` as lazy routes: tasks (I02-light), new event (I05), dossier head (I07-light) with poster upload,
guard list and transition buttons. M2 adds `features/admin` (`/verwaltung/kategorien|orte|organisationen` I23,
`/verwaltung/zuordnungen` I24) behind `core/auth/permission.guard.ts` (`permissionGuard(...perms)`, refused routes go to
`/forbidden`), its strings in `core/i18n/translations.admin.de.ts`, and "Andere Sitzungen widerrufen" on `/konto`.

**Rules:**
- Angular 20, standalone, OnPush, signals, strict TS, separate `.html` and `.scss`, Jest + Testing Library + jest-axe.
- UI kit: `@stupa-makers/ui-kit` from the git submodule `frontend/vendor/ui-kit` (pinned `8ad3782`), compiled through
  the tsconfig path mapping. Run `git submodule update --init --recursive` before `npm ci`/`npm run build`.
- Strings are German i18n keys (colon or neutral gender). Guard messages use `messageKey` (`guards.<code>`) from
  the API, never the server's text.
- API types are written by hand from `docs/M1-KONTRAKT.md` section 4.2 and `docs/M2-KONTRAKT.md` section 2.1,
  camelCase, identical names.
- Navigation and guards ask permissions (`/auth/me` `permissions`), never role names; the server stays the gate.
- Dev proxy: `ng serve` on 4200 forwards `/api` to the backend (`proxy.conf.json`); the Keycloak and Authentik clients
  accept `http://localhost:4200/api/auth/callback`.
- Build budgets fail the Docker build but not jest or tsc: run `npm run build` after CSS changes. Check light and dark
  against the production build.

**Gates:** `npm run lint`, `npm run typecheck` (app and specs), `npm test` (coverage thresholds in `jest.config`), `npm run build`,
E2E `npx playwright test` (browsers from `nix build nixpkgs#playwright-driver.browsers`, against the compose stack or `ng serve` with `E2E_BASE_URL`; `m1.spec.ts`, `m2.spec.ts`).

**Traps:** nginx serves the SPA only; `/api`, `/ics/`, `/e/`, `/k/`, `/suche` go to the API (`deploy`). The
Angular service worker must see `ngsw.json` uncached; `/manifest.webmanifest` is dynamic and not an asset group.

**Siblings:** `be-auth` (login flow), `be-pipeline` (reasons), `deploy`.
