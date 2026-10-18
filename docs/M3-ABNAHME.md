# M3-Abnahme: Protokoll vom 18.10.2026

Lauf auf dem Entwicklungsrechner (NixOS, Docker lokal), Branch `feat/m2-rollen`, nicht committet. Kein Live-System
berührt: IdP ist der lokale Keycloak, alle Daten liegen in lokalen Containern. Kriterium wörtlich:
`docs/M3-KONTRAKT.md` Abschnitt 10.1. Backend- und Frontend-Builder haben ihre Teile geliefert; der Integrationslauf
(Abschnitt I) hat alles erneut ausgeführt, die Verdrahtung korrigiert und die Ergebnisse unten belegt.

## Ergebnis

| Teil des Kriteriums | Ergebnis | Beleg |
|---|---|---|
| Vollmatrix Zustand × Übergang × Rolle × Bild × Vier-Augen | erfüllt: 14 Übergänge × 8 Zustände × 10 Akteure × 3 Bildlagen × 3 Vier-Augen-Lagen × 2 Uhren × 2 Notizlagen gegen das unabhängige Orakel | `test_transitions_matrix.py` (ein Test je Übergang, der das ganze Produkt abläuft), `oracle.py`; über HTTP `test_rbac_transitions.py` (14 Übergänge × 12 Nutzer, exakte Statuscodes) |
| U-GUARD-01 bis 13 | erfüllt | `test_u_guard.py` (01, 02, 03, 04, 06, 07, 09, 10, 11, 12), `test_u_guard_integration.py` (05, 07, 08, 13) |
| Property "kein `live` ohne Bild" | erfüllt, 200 Beispiele, alle Übergänge, Aktionen, Worker-Läufe | `test_publish_property.py` |
| trusted Approver gibt eigene Einreichung nicht frei | erfüllt: 403 `four_eyes`; zweite Person 200; Direkt-INSERT scheitert mit 23514 | `test_four_eyes.py`, A (b), Playwright "Four eyes" |
| Organisator:in korrigiert Kurztext in `live`, Uhrzeit nur Redaktion | erfüllt | `test_field_classes_api.py`, A (d), Playwright "Field classes in live" |
| Absage bleibt im Feed als `cancelled` | erfüllt; nach `reinstate` wieder `scheduled` | `test_public_feed.py`, `test_actions.py`, A (e), Playwright "Cancellation" |
| Board per Tastatur bedienbar | erfüllt: Leertaste greift, Pfeil wechselt Spalte, Ansage im Live-Bereich, Escape legt zurück, geschlossene Spalte "nicht möglich", Ablage öffnet I13 | Playwright "Board: keyboard drag", "Phone: tabs, swipe and the move sheet"; Jest `pipeline-board` |
| axe grün, Hell und Dunkel, Produktions-Build | erfüllt: 0 Befunde `serious`/`critical` auf `/aufgaben`, `/pipeline`, `/dossiers`, Dossier in `planning`/`in_review`/`live`, I05, I13, I14, I15, Konfliktdialog, Board am Handy; je Hell und Dunkel | D2 (Image aus `deploy/web/Dockerfile`, nginx auf 8081) |
| Autosave überlebt Reload | erfüllt: Eingabe, Anzeige "Gespeichert hh:mm", Reload, Text steht im Feld; zweite Sitzung speichert, Dreiwege-Dialog | Playwright "Autosave survives a reload", `test_autosave.py`, A (g) |
| 100 % Branch `pipeline` | erfüllt | `coverage_critical`: ok (0 file(s) below 100 %), Gesamt 98,29 % |
| Worker | erfüllt: geplanter Lauf (i), überfälliges `publish_at` (k) wird `live`, Ende vor 13 h (l) wird `followup`; Viertelstunden-Cron läuft im Log | A (i, k, l), `test_advance_states.py` |

## A: API-Abnahme (`backend/scripts/m3_acceptance.py`)

Echter OIDC-Flow gegen den Dev-Keycloak für `organizer-fsi`, `editor`, `member`, `approver-stupa`,
`approver2-stupa`. SQL nur für Datumsspalten (k, l) und den Netz-Test (j). Die Worker-Schritte stellen
`advance_states` einmal als arq-Job in die Warteschlange des laufenden `stupa-worker` (`scripts/m3_worker.py`) und
lesen dessen Logzeile; `M3_WAIT_CRON=1` wartet stattdessen auf den nächsten Viertelstundenlauf. Gekürzt:

```
$ uv run --env-file .env python -m scripts.m3_acceptance
[m3] realm sync created 0 missing group(s) or user(s)
[m3] ok   b: approver-stupa gets 403 four_eyes on the own dossier
[m3] ok   b: approver2-stupa approves and publishes
[m3] ok   c: the editor approved and published the fsi dossier
[m3] ok   d: organizer corrects the summary in live -> 200
[m3] ok   d: organizer cannot move the time -> 409      (field_locked)
[m3] ok   d: the editor moves the time -> 200
[m3] ok   e: the feed shows 'cancelled'
[m3] ok   e: reinstate keeps live and sets the public status back to scheduled
[m3] ok   e: the feed shows 'scheduled'
[m3] ok   f: the extra proposal is proposal_quota_exceeded
[m3] ok   g: the draft is intact                         (PUT draft, GET draft nach "Reload")
[m3] ok   g: PATCH cleared the draft
[m3] ok   g: the stale draft is a conflict carrying the current version
[m3] ok   g: the stale PATCH is a conflict and changes nothing
[m3] ok   h: T03 without a note is reason_required / T07 / the editor restores with T12
[m3] ok   j: UPDATE state='live' without an image fails with 23514
[m3] worker advance_states: published=2 followup=0 archived=0 blocked=0 skipped=0 failed=0
[m3] ok   i: the worker published it, it is in the feed
[m3] worker advance_states: published=1 followup=0 archived=0 blocked=0 skipped=0 failed=0
[m3] ok   k: the worker set the overdue dossier live
[m3] worker advance_states: published=0 followup=1 archived=0 blocked=0 skipped=0 failed=0
[m3] ok   l: an event that ended 13 hours ago is in followup
[m3] M3 acceptance: all checks passed                  (140 Prüfzeilen)
```

`published=2` im ersten Lauf: das Zeitplan-Dossier eines abgebrochenen Vorlaufs (siehe I4) war ebenfalls fällig.
Der Vollzyklus `idea → planning → in_review → approved → live → cancel → reinstate` steckt in (c) bis (e), die
Rücksprünge T03, T06, T07, T11, T12 in (h). Der Fall "Poster wird ungültig, Dossier bleibt `approved`" braucht einen
abgeschalteten Trigger und bleibt bei `test_a_poster_that_turned_invalid_blocks_the_worker`.

Viertelstunden-Cron im Log des `stupa-worker` (ohne Zutun des Skripts):
`17:30:00 cron:advance_states ● 'published=0 followup=0 archived=0 blocked=0 skipped=0 failed=0'`.

`m1_acceptance.py` und `m2_acceptance.py` laufen weiter grün (I3).

## B: Backend-Gates

```
$ uv run alembic heads                               -> 0004_pipeline_full (head)
$ uv run alembic current   (Dev-DB)                  -> 0004_pipeline_full (head)
$ psql -f /db/roles.sql    (Dev-DB, Stufe 2)         -> ohne Fehler (ON_ERROR_STOP)
$ ruff check . / ruff format --check .               -> All checks passed! / 310 files already formatted
$ basedpyright                                       -> 0 errors, 0 warnings, 0 notes
$ pytest -m 'not integration and not e2e and not live'
                                                     -> 1266 passed
$ PROVENANCE_STRICT=1 pytest -m 'not e2e and not live' --cov
                                                     -> 1659 passed in 834 s, Coverage 98,30 % (Gate 90 %)
$ python -m scripts.coverage_critical                -> coverage_critical: ok (0 file(s) below 100 %)
$ python -m scripts.seed_dev   (zweimal)             -> 0 new group mapping(s) / 0 new dossier(s)
$ deploy/compose-lint.sh                             -> compose-lint ok
```

Die Zahl der Testfälle ist kleiner als in M2 (2536), weil `test_transitions_matrix.py` nicht mehr 1296 parametrisierte
Fälle erzeugt, sondern je Übergang einen Test, der das ganze Produkt gegen das Orakel prüft und alle Abweichungen auf
einmal meldet (32 Testfälle, mehr Zellen als vorher).

## D: Frontend

```
D1 $ npm run lint                                     -> eslint ohne Befund
   $ npm run typecheck                                -> tsc app + spec ohne Fehler
   $ npm test                                         -> 114 Suites, 984 passed, 1 skipped, 1 todo
   $ npx jest --coverage                              -> 98,9 / 94,86 / 98,08 / 99,5 (Schwellen 97/94/97/98)
   $ npm run build                                    -> Produktions-Build ohne Fehler
   $ E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m1.spec.ts e2e/m2.spec.ts e2e/m3.spec.ts
                                                      -> 17 passed (4,2 min)
D2 Produktions-Build hinter nginx (siehe I5):
   $ E2E_BASE_URL=http://localhost:8081 npx playwright test e2e/m1.spec.ts e2e/m2.spec.ts e2e/m3.spec.ts
                                                      -> 17 passed (2,4 min), axe Hell und Dunkel inklusive
```

m3-Szenarien: Board per Tastatur, Handy (Tabs, Wischen, Bewegen per langem Druck), Vier-Augen, Feldklassen in
`live`, Absage im Feed und Rücknahme, Autosave mit Reload und Konflikt, Vorschlag mit Organisationszuweisung, axe.

## I: Integrationslauf (18.10.2026)

Aufbau: Dev-Stack (`docker-compose.dev.yml`, Postgres, Redis, MinIO, ClamAV, Keycloak healthy), API und Worker als
`systemd-run --user`-Units `stupa-api`/`stupa-worker` mit `backend/.env` und `LD_LIBRARY_PATH` (libstdc++, libmagic),
`ng serve :4200`, Playwright-Browser aus `nixpkgs#playwright-driver.browsers`.

```
I1 alembic upgrade head (ein Head), roles.sql, seed_dev zweimal, systemctl --user restart stupa-api stupa-worker
I2 Gates B und D1 grün (zweimal: vor und nach den Korrekturen)
I3 m1_acceptance / m2_acceptance / m3_acceptance  -> all checks passed
I4 Fund: ein zweiter arq-Worker (M2-Code, seit 13:48 in einem Terminal) hing an derselben Warteschlange `events` und
   nahm einen Teil der Jobs an: "JobExecutionFailed: function 'advance_states' not found". Prozess beendet;
   `pgrep -af 'arq worker'` zeigt nur noch `stupa-worker`. Danach m3_acceptance grün.
I5 Produktions-Build: Image `stupa-events-web:m3-axe` aus `deploy/web/Dockerfile` (npm ci, ng build, nginx 1.27),
   gestartet mit `--network host` und den echten `nginx.conf`, `security-headers.conf`, `api-proxy.conf`; geändert
   sind nur `listen 127.0.0.1:8081` und das Upstream `127.0.0.1:8001`. Dahinter eine zweite API-Instanz
   (Unit `stupa-api-web`, gleiche DB) mit PUBLIC_BASE_URL und OIDC-Redirect auf `http://localhost:8081`, damit der
   Login zurück auf 8081 führt. Der volle Compose-`web` hätte eine eigene leere Datenbank ohne Seeds und ohne
   Keycloak-Overlay (der Dev-Keycloak belegt 8090).
   curl: `/` 200, `/pipeline` 200 mit CSP aus security-headers.conf, `/api/health` mit genau einer CSP-Zeile.
I6 gitleaks dir: zwei Treffer in `deploy/secrets/backup-age.key` (lokaler Schlüssel, per .gitignore ausgeschlossen,
   nie im Index); sonst keine.
```

Korrekturen im Integrationslauf:

- **Karten-Blocker = Übergangs-Blocker:** `EventCard.blockers` rechnete ohne Quarantäne-Anhänge, `followup`-Eintritt
  und wiederverwendetes Poster; die Karte konnte "frei" zeigen, wo T04 mit 422 scheitert. Neu
  `app/modules/events/card_extras.py` (drei gruppierte Abfragen je Seite), `test_card_guards.py` (rot ohne die
  Korrektur, grün mit ihr). Kontrakt 12.21.
- **`m3_acceptance.py`** erweitert: Worker einmal von Hand statt 17 Minuten Warten, (k) überfälliges `publish_at`,
  (l) Ende vor 13 h, `reinstate` zurück auf `scheduled` im Feed, 409 `conflict` auf veralteten Entwurf und PATCH.
- **`m2_acceptance.py`**: Listenprüfung blättert alle Seiten (`listed_ids`); mit den vielen Dossiers der Dev-DB lag
  das neue Dossier nicht mehr auf Seite 1 (Sortierung `startsAt`, 50 je Seite) und der Lauf scheiterte.
- **`test_provenance.py`** übergeht `test-results/` und `playwright-report/`; eine Playwright-Trace-Datei mit
  Upstream-Kopfzeile ließ `PROVENANCE_STRICT=1` scheitern, während Playwright parallel lief.
- **`PROVENANCE.frontend-m3.json`** in `PROVENANCE.json` gemischt (20 Einträge, sortiert), Datei entfernt; Skill
  `frontend` angepasst. Skill `be-pipeline`: Fallen "Karten-Snapshot" und "zweiter Worker".

Weiter laufend: `stupa-api` (:8000), `stupa-worker`, `ng serve :4200`, dazu für die Prüfung am Produktions-Build
`stupa-api-web` (:8001) und der Container `stupa-events-web-axe` (:8081). Abbau:
`systemctl --user stop stupa-api-web; docker rm -f stupa-events-web-axe`.

## R: Review-Runde (18.10.2026)

Behoben: Revert in gesperrten Zuständen (Blocker), Live-Guards bei `summary`, Link-Hosts, Worker-Kandidaten pro Lauf
paginiert, Entwurfs-Body gestreamt, Autosave hält bei 4xx an, `saveFirst` nur in `idea`/`planning`, Absagen-Dialog über
`allowedActions`, "Nachträglich geändert" per `minRev`, Pflicht-`If-Match` (428), `postpone`-Guards, `tasks`-Abfragen,
echter `Committed` beim PATCH, Live-Regeln des Boards (polite/assertive, Menü-Knopf auf dem Handy), Maskierung der
Revisionen. Dazu ein Befund der neuen API-Irrfahrt (`tests/integration/pipeline/test_api_walk.py`): ein Prüfender konnte
`summary` in `in_review` leeren und freigeben, T04 prüft jetzt `hasField` erneut. Die Irrfahrt fängt den alten
Revert-Fehler (Mutationsprobe), das Hypothesis-Modell hat eine Inhalts-/Revert-Regel.

## Offen

- T07 setzt `public_status` auf `scheduled` zurück (Abnahme-Abweichung): Luis entscheidet, ob die Absage bei
  "Offline nehmen" erhalten bleibt (Empfehlung: ja, nur `reinstate` setzt zurück).

- Platzhalter-Guards (Kontrakt 12.18): Dubletten, Kommentare am Poster, Checklisten, `facts`, Nachbereitungsfelder,
  Standort-Bestätigung, Wandzeit-Warnungen und `openCommentRequired` melden "erfüllt", bis M4 bis M6 die Daten liefern.
  `open_comment_required` blockt nur bei `open_comments == 0`, nicht bei `None`. Für sieben der 15 `fixAction`-Werte
  zeigt das Frontend keinen Knopf (keine bedienbare Aktion in M3).
- Abweichungen der Builder, die Luis entscheiden sollte: Konfliktdialog bietet je Feld "Deins behalten"/"Neu
  übernehmen" (Kontrakt 8.6 nennt nur Neu laden); CanDeactivate fragt nur bei ungesendeten Änderungen; T07 setzt
  `public_status` auf `scheduled` zurück; No-op-PATCH erzeugt keine Revision; Warnungen `end_estimated`,
  `time_ambiguous`, `time_gap` stehen bei T02 und T04 (Tabelle 2.3 statt 2.2).
- nginx und CSP sind am echten Image geprüft, aber nicht im vollen Compose-Stack mit eigener Datenbank (I5). Vor dem
  Pilot einmal `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.keycloak.yml up --build` mit
  freiem 8090.
- Der Dev-Vorschlag gehört `member`, sobald sich diese Person einmal angemeldet hat; vorher dem Ersatz `seed-member`.
- `app/modules/events/{cards,card_extras,listing}.py` und `tasks/*` liegen nicht unter `coverage_critical`, sind aber
  durch Integrationstests abgedeckt.
- Nichts committet. Der Branch `feat/m3-pipeline` entsteht beim Commit-Schritt; die Löschung von
  `pipeline/guards.py` (jetzt Paket `guards/`) steht nur im Arbeitsbaum.
