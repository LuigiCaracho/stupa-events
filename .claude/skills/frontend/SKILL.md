---
name: frontend
description: Angular 20 app of STUPA Events (frontend/). Shell, auth, i18n, theme, PWA update, the ui-kit submodule, the M1 feature pages, the M2 admin area (taxonomy, group mappings, session revoke), the M3 pipeline (board I03, tasks I02, list I04, dossier I07 with field locks, autosave, edit conflict and history, dialogs I13 to I15) and the build and test gates. Use when working on any file under frontend/, on routing, translations or the API client types.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/frontend/SKILL.md (adapted). -->
# Frontend: `frontend/`

**Does:** Single-page PWA. The shell (`core/`, `shared/ui`) owns routing with frames `rail`, `public`, `bare`,
`pending`, auth state, i18n (de), theme and the service-worker update prompt. Features live in
`src/app/features/**` as lazy routes. M3 (`docs/M3-KONTRAKT.md` section 8):

- `features/pipeline`: `/pipeline` board (I03) with `shared/ui/pipeline-board` (CDK drag into the columns that
  `card.moves` names, keyboard lift with Space and the arrows, phone tabs with scroll-snap pager and a long press
  that opens `move-sheet`), `filters/` (URL-backed filter state shared with the list), `board-card/`.
- `features/tasks`: `/aufgaben` (I02) from `GET /api/tasks`, one `task-section` per group.
- `features/dossiers`: list I04 (`/dossiers`, the dossier `:id` is its child route beside the list), new event or proposal
  I05, dossier I07 split into `head/` (state bar, primary button, menu "Mehr"), `overview/` ("Fehlt noch", lock notes, banner
  "Nachträglich geändert"), `form/` (locks from `editableFields` and `lockReason`), `autosave/` (`DraftAutosave` class),
  `conflict/` (three-way dialog), `history/`; dialogs `transition/` (I13), `cancel/` (I14), `exception/` (I15),
  `reason/`, `assign/`. `detail/` holds the page and `detail-dialogs`. `core/auth/pending-changes.guard.ts` asks the page
  `canLeave()`.
- M2 `features/admin` (`/verwaltung/...`) behind `permissionGuard(...)`, strings in `translations.admin.de.ts`.

**Rules:**
- Angular 20, standalone, OnPush, signals, strict TS, separate `.html` and `.scss`, Jest + Testing Library + jest-axe.
- UI kit: `@stupa-makers/ui-kit` from the git submodule `frontend/vendor/ui-kit` (pinned `8ad3782`), compiled through
  the tsconfig path mapping. Run `git submodule update --init --recursive` before `npm ci`/`npm run build`.
- Strings are German i18n keys (colon or neutral gender). Guard messages use `messageKey` (`guards.<code>`) from
  the API, never the server's text.
- API types are written by hand from `docs/M1-KONTRAKT.md` 4.2, `docs/M2-KONTRAKT.md` 2.1 and `docs/M3-KONTRAKT.md` 5.1,
  camelCase, identical names (`board.models.ts`, `task.models.ts`, `action.models.ts`, `event.models.ts`).
- Writes carry the revision as `If-Match: "<rev>"`; the server answers 409 `conflict` with `current`. A change in the form
  is autosaved as a draft after 15 s (`PUT .../draft`), saved for good only by "Speichern", a transition or 30 min idle in
  `idea`/`planning`. Unknown `fixAction` values show no button (`HANDLED_FIXES` in `reason-text.ts`).
- One `h1` per page: the dossier title is the `h1` of `/dossiers/:id`, the list header becomes a plain `p` while a dossier is open.
- Navigation and guards ask permissions (`/auth/me` `permissions`), never role names; the server stays the gate.
- Dev proxy: `ng serve` on 4200 forwards `/api` to the backend (`proxy.conf.json`); the Keycloak and Authentik clients
  accept `http://localhost:4200/api/auth/callback`.
- Build budgets fail the Docker build but not jest or tsc: run `npm run build` after CSS changes. Check light and dark
  against the production build.

**M4 (dossier and knowledge, `docs/M4-KONTRAKT.md` 6 and 7):**
- Tabs of `/dossiers/:id`: Übersicht, Anhänge, Anleitung, Checkliste, Mails, Verlauf (a `tab` signal in `dossier-detail`, not child
  routes; counters from `GET /events/{id}/dossier-counts`, threads from `GET /events/{id}/comments`). Each tab is a component under
  `features/dossiers/{attachments,howto,checklist,mails,activity}` with `event`, `canEdit` and a `changed` output that refreshes counters and guards.
- Editor shell `features/dossiers/editor/dossier-markdown-editor`: "Editor | Quelltext" over one Markdown value. Tiptap
  (`@stupa-makers/ui-kit/markdown-editor`, tsconfig and jest alias) is imported only by `rich-editor.component.ts`, which the shell loads
  with `@defer`, so it stays in a lazy chunk (check `npm run build`). In specs of a page that mounts the shell use `deferBlockBehavior: Playthrough`.
- Roundtrip gate E20: `npm run gate:roundtrip [-- --write]` runs `shared/markdown/roundtrip.gate.spec.ts` over
  `frontend/tests/fixtures/markdown/*.md` (30 files) and the stored decision `shared/markdown/roundtrip-gate.json` (`passed`, `failed[]`, `corpusHash`,
  `kitCommit` = hash of the kit's editor sources). `passed = false` (as measured: Tiptap drops the final newline, escapes `[ ]` task lists, joins
  soft breaks, rewrites reference links and indented code) makes the Markdown source the default mode; the editor stays a switch, and a text that does not
  survive is sent back to the source with a note (`kit-roundtrip.ts` reaches into the kit's private editor once, for gate and runtime check).
  Never edit the corpus to make it pass; rerun with `--write` after a kit or corpus change.
- Timers (draft autosave, bell polling) start outside the Angular zone, so they do not block `fixture.whenStable()`.
- Number formats go through `shared/format.util.ts` (`Intl`), not `CurrencyPipe`/`DecimalPipe` (no `registerLocaleData('de')`).
- Bell and inbox: `features/notifications` (store with 60 s poll while the tab is visible and on route change), bell button in nav rail and phone bar.
  Preferences: `features/account/notification-prefs`. A ui-kit switch keeps its own state, so a rollback re-renders the rows (`rollbacks` signal).
- `app-button` takes `[ariaPressed]`, not `[attr.aria-pressed]` (the attribute would land on the host, not the button).

**Gates:** `npm run lint`, `npm run typecheck` (app and specs), `npm test` (coverage thresholds in `jest.config`), `npm run build`,
E2E `npx playwright test` (browsers from `nix build nixpkgs#playwright-driver.browsers`, against the compose stack or `ng serve` with `E2E_BASE_URL`; `m1.spec.ts`, `m2.spec.ts`, `m3.spec.ts`, `m4.spec.ts`). `m3.spec.ts` ends with axe (`@axe-core/playwright` 4.13.0, light and dark, contrast included); run it against the production build of the compose `web` container.

**Traps:**
- `ng serve` can keep serving a stale bundle after a lockfile change; restart it when the nav lacks a new entry.
- A copied upstream file carries `Copied from STUPA-Workflow@93c33d6 <path>` and an entry in `PROVENANCE.json`
  (builder parts `PROVENANCE.<builder>.json` are merged there by the integration run).
- `DraftAutosave.reset()` keeps the offline text in `localStorage` (it is read right after); only `discard()` and a
  successful save clear it. A timer inside the page makes `fixture.whenStable()` hang: use fake timers in such specs. nginx serves the SPA only; `/api`, `/ics/`, `/e/`, `/k/`, `/suche` go to the API (`deploy`). The
Angular service worker must see `ngsw.json` uncached; `/manifest.webmanifest` is dynamic and not an asset group.

**Siblings:** `be-auth` (login flow), `be-pipeline` (reasons), `deploy`.
