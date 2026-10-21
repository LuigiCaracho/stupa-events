---
name: frontend
description: Angular 20 app of STUPA Events (frontend/). Shell, auth, i18n, theme, PWA update, the ui-kit submodule, the admin area, the event list with its calendar, the one-page dossier (poster slot, hints, anchor sections, small cancel dialog), the dossier knowledge (attachments, howto, checklist, mails, quotes, "So lief es"), the archive (clone, formats, library, search and palette) and the build and test gates. Use when working on any file under frontend/, on routing, translations or the API client types.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/frontend/SKILL.md (adapted). -->
# Frontend: `frontend/`

**Does:** Single-page PWA. The shell (`core/`, `shared/ui`) owns routing with frames `rail`, `public`, `bare`,
`pending`, auth state, i18n (de), theme and the service-worker update prompt. Features live in
`src/app/features/**` as lazy routes. Since M5b (`docs/M5B-KONTRAKT.md` 10) the product is the event dossier, not a pipeline:

- `features/dossiers/list`: `/dossiers` is the start page: "Neues Event" and "Neu aus Vorlage", filter chips (organization, category,
  state, year, "Nur meine", URL-backed in `filters/event-filters.ts`), the switch Liste | Kalender (`?ansicht=kalender`), cards with
  thumbnail or placeholder. `features/calendar/view` is the embedded calendar (no `/kalender` route). `/dossiers/neu` opens the dialog
  over the list (`?vorlage=<id>` the clone dialog).
- `features/dossiers/detail`: `/dossiers/:id` is ONE page, top to bottom: `head/` (title, state as text, the action bar = exactly
  `allowedActions`, nothing is computed on the client), the banner "Ohne Bild nicht bewerbbar", `hints/hint-list` ("Fehlt noch", plain list from
  `GET /events/{id}/hints`, never a blocker, "Ergänzen" jumps to the field), `poster/poster-slot` (large, drop or pick, replace, remove),
  `section-nav` (sticky anchors, keyboard reachable), then the sections with an `id` each: Eckdaten (`form/`, open for `draft`, closed otherwise),
  Doku (`howto/`), Anhänge, Checkliste, Mails, Angebote, So lief es (`outcome/`: retrospective, result, "Anleitung geprüft"), Verlauf
  (`history/`, `activity/`). Lifecycle calls (`publish`, `unpublish`, `archive`, `restore`) are one click; `cancel/` is the only dialog (cancel, postpone,
  reinstate with the public reason). `conflict/`, `autosave/` and `core/auth/pending-changes.guard.ts` stay.
- M2 `features/admin` (`/verwaltung/...`) behind `permissionGuard(...)`, strings in `translations.admin.de.ts`.

**Rules:**
- Angular 20, standalone, OnPush, signals, strict TS, separate `.html` and `.scss`, Jest + Testing Library + jest-axe.
- UI kit: `@stupa-makers/ui-kit` from the git submodule `frontend/vendor/ui-kit` (pinned `8ad3782`), compiled through
  the tsconfig path mapping. Run `git submodule update --init --recursive` before `npm ci`/`npm run build`.
- Strings are German i18n keys (colon or neutral gender). Hint texts are `hints.<code>`; the server sends codes, never text.
- API types are written by hand from `docs/M5B-KONTRAKT.md` 7 (`card.models.ts`, `action.models.ts`, `event.models.ts`), camelCase.
- Writes carry the revision as `If-Match: "<rev>"`; the server answers 409 `conflict` with `current`. A change in the form
  is autosaved as a draft after 15 s (`PUT .../draft`), saved for good only by "Speichern" or an action.
- One `h1` per page: the dossier title is the `h1` of `/dossiers/:id`.
- A `linkedSignal` that reads the whole event resets on every save; derive it from `computed(() => event()?.state)` (Eckdaten open state).
- Navigation and guards ask permissions (`/auth/me` `permissions`), never role names; the server stays the gate. Nav: Events, Archiv,
  Formate, Bibliothek, Verwaltung, Konto; the phone bar holds the first four, the bell and "Mehr" (`BOTTOM_BAR_KEYS`).
- Dev proxy: `ng serve` on 4200 forwards `/api` to the backend (`proxy.conf.json`); the Keycloak and Authentik clients
  accept `http://localhost:4200/api/auth/callback`.
- Build budgets fail the Docker build but not jest or tsc: run `npm run build` after CSS changes. Check light and dark
  against the production build.

**M4 (dossier and knowledge, `docs/M4-KONTRAKT.md` 6 and 7):**
- Sections of `/dossiers/:id`: Eckdaten, Doku, Anhänge, Checkliste, Mails, Angebote, So lief es, Verlauf (anchors, not tabs; counters from `GET /events/{id}/dossier-counts`, threads from `GET /events/{id}/comments`). Each tab is a component under
  `features/dossiers/{attachments,howto,checklist,mails,activity}` with `event`, `canEdit` and a `changed` output that refreshes counters and hints.
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

**M5 (archive, template, search, calendar, `docs/M5-KONTRAKT.md` 3 to 7 and 11):**
- `features/archive`: `/archiv` (I20: URL-backed filters in `page/archive-filters.ts`, `shared/url-state.ts` is the generic URL state with the 250 ms typing delay,
  scope Dossiers | Dokumente | Formate, facets as `app-filter-select` with counts, hits as `app-search-hit`), `/archiv/:id` is the read-only page of an archived dossier
  of another organization (`GET /api/archive/{id}`), `last-time/` the card "Letztes Mal", `preview/carry-over-list` the lines of the carry-over table.
  Highlights are `{text, hit}` segments drawn as `<mark>` by `shared/ui/highlighted` (never `innerHTML`); hits without a server highlight are marked by `highlight-terms.ts`.
- `features/dossiers/clone`: I06 "Neu aus Vorlage" (`/dossiers/neu?vorlage=<id>`, `?format=<slug>` or `?modus=vorlage`) over the dossier list; the dialog I05 and I06 switch
  through the segmented control "Neu | Aus Vorlage"; hits are grouped by format on the client (`template-groups.ts`); phone: list, then preview and form.
- `features/formats` (I18, list-detail like the dossiers, master howto in `dossiers/editor/document-editor`), `features/library` (I19, `/bibliothek/:kind/:id` is the same page
  with an open item, "In Dossier übernehmen" in `adopt/`), `features/calendar` + `shared/ui/calendar-grid` (month/week grid with roving tabindex, "+n" sheet, agenda list under 768 px,
  `CALENDAR_NOW` token clock, day keys instead of instants in `calendar-grid.util.ts`; `calendar/model/calendar-entries.ts` fills local days the server leaves out).
- Palette: `layout/palette` (`PaletteService` and the Strg/Cmd+K handler sit in the shell; the component loads lazily with `@defer (when palette.requested())`, so the initial bundle stays small).
  `DossierCommands` (`features/dossiers/api/dossier-commands.ts`) carries "Als Format speichern" from the palette to the open dossier.
- Dossier parts: `outcome/` (retrospective document created on the first save, result form `outcome-model.ts` with euros in the form and cents on the wire, "Anleitung geprüft"; voluntary and writable in the archive), `facts/` the "Rahmen" by profile of the main category (`facts-profiles.ts`), `location/` "Ort bestätigen", `format-save/` "Als Format speichern", `overview/last-time-block` and `template-panel`. Hint codes map to targets in `dossier-detail.fix()`.
- `resourceValue(resource, fallback)` (`core/api/resource-value.ts`) reads a resource without throwing in the error state; use it instead of `hasValue() ? value() : x`.
- Trap: `<app-checkbox id="x">` puts the id on the host and the input (label broken); bind `[id]="'x'"`. A highlighted title is split into text nodes: find a hit by `getByRole('article', { name })`.

**Gates:** `npm run lint`, `npm run typecheck` (app and specs), `npm test` (coverage thresholds in `jest.config`), `npm run build`,
E2E `npx playwright test` (browsers from `nix build nixpkgs#playwright-driver.browsers`, against the compose stack or `ng serve` with `E2E_BASE_URL`; `m1.spec.ts` to `m5b.spec.ts`; helpers in `e2e/support/dossier.ts`). `m5b.spec.ts` and `m3.spec.ts` run axe (`@axe-core/playwright` 4.13.0, light and dark, contrast included); run it against the production build of the compose `web` container. The crowded dev DB hides entries: filter by title (`?q=`) before looking for a card or a calendar day.

**Traps:**
- `ng serve` can keep serving a stale bundle after a lockfile change; restart it when the nav lacks a new entry.
- A copied upstream file carries `Copied from STUPA-Workflow@93c33d6 <path>` and an entry in `PROVENANCE.json`
  (builder parts `PROVENANCE.<builder>.json` are merged there by the integration run).
- `DraftAutosave.reset()` keeps the offline text in `localStorage` (it is read right after); only `discard()` and a
  successful save clear it. A timer inside the page makes `fixture.whenStable()` hang: use fake timers in such specs. nginx serves the SPA only; `/api`, `/ics/`, `/e/`, `/k/`, `/suche` go to the API (`deploy`). The
Angular service worker must see `ngsw.json` uncached; `/manifest.webmanifest` is dynamic and not an asset group.

**Siblings:** `be-auth` (login flow), `be-lifecycle` (states and actions), `deploy`.
