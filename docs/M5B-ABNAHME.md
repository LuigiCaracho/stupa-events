# Abnahme M5b: Rückbau zum Event-Dossier

Stand 2026-10-22, Branch `feat/m5b-vereinfachung` (von `feat/m5-archiv` @ `aebf331`), nichts gepusht. Grundlage:
`docs/M5B-KONTRAKT.md` Abschnitt 11. Alles lief lokal: Dev-Dienste aus `deploy/docker-compose.dev.yml`, API und Worker
als User-Units (`stupa-api`, `stupa-worker`), `ng serve` auf 4200, Keycloak 8090 mit echten OIDC-Logins. Kein
Live-System berührt.

## Ergebnis

Abnahmesatz (Kontrakt 11) **erfüllt**, mit den offenen Punkten unten. Ein Event lässt sich ohne Pipeline von Entwurf bis
Archiv führen; `organizer-fsi` legt an, schreibt die Anleitung, lädt ein Poster hoch und veröffentlicht selbst; ohne
Poster gibt `publish` 200, der Hinweis `no_poster` steht mit `warn` in `GET /hints` und der Feed liefert `image: null`.
Die Migration `0007` überführt alle acht Altzustände. Feed, ICS, Kanarienvogel und Schemathesis sind grün.

| # | Prüfpunkt | Ergebnis | Beleg |
|---|---|---|---|
| a | Pfad organizer-fsi mit Doku, Poster, `publish`, Feed mit Bild; ohne Poster 200, `no_poster`, `image: null` | erfüllt | `m5b_acceptance` a (`m5b_dossier.check_doc_path`, `check_lifecycle`), Playwright m5b 1 und 2 |
| b | submitter 403, organizer-makers 404 (Lesen und `publish`), editor veröffentlicht fremdes Event, `restore` nur editor; `publish_requires_editor` | erfüllt; `publish_requires_editor` nur im Backend-Test (Kontrakt 9) | `m5b_acceptance` a, b; `test_flow.py::test_publish_requires_editor_…`, `test_lifecycle_matrix.py` |
| c | `cancel`/`postpone`/`reinstate`: Feed-Status, ICS `CANCELLED`/`TENTATIVE`, `SEQUENCE` steigt | erfüllt | `m5b_acceptance` a, c |
| d | Worker `archive_ended` nach Ende + 12 h, `actor_type = system`; Doku im Archiv schreibbar, Eckdaten 409 | erfüllt | `m5b_acceptance` a, b; `tests/integration/archive/test_followup.py` |
| e | Migration `0007` auf Altdaten, Zahlen je Zustand | erfüllt | Abschnitt A |
| f | entfernte Routen 404 | erfüllt (alle 404; `?view=board` 422, weil `view` ein Literal ist) | `m5b_acceptance` f (`m5b_rights.check_gone`), `test_route_authz_inventory.py` |
| g | Suche (20 Mustersuchen), Klon "Neu aus Vorlage" (Entwurf mit Anleitung), Format speichern, Bibliothek | erfüllt | `m5b_acceptance` g, Playwright m5b 3, m5 |
| h | Feed-Cache: Veröffentlichen baut neu; Kategorie-Umbenennung invalidiert sofort | erfüllt; Orts-, Organisations- und Scan-Pfad nur in Integrationstests | `m5b_acceptance` f, h; `tests/integration/publicapi/test_cache_invalidation.py` |
| i | Playwright m5b und bereinigte m1 bis m5, 360 px und Desktop, hell und dunkel, axe | erfüllt gegen `ng serve`; axe gegen Produktions-Build hinter nginx nicht gelaufen | Abschnitt B |
| j | Gates | erfüllt | Abschnitt B |
| k | Aufräumprobe | erfüllt | Abschnitt C |

## A: Migration 0007 auf echten Altdaten

Die Dev-DB stand bereits auf `0007` (der Backend-Builder hatte sie migriert; ihre `migration-0007`-Statuszeilen zeigen
sieben Altzustände plus vorhandene `archived`). Für einen sauberen Nachweis lief die Migration noch einmal auf einer
Kopie: das letzte M5-Backup (`/tmp/m5-backups/20261020T123657Z`, Revision `0006_archive_feed`) in einen Wegwerf-Container
zurückgespielt, Zählung, `alembic upgrade head`, Zählung (Skript `/tmp/m5b-int/replay.sh`, Container danach entfernt).

```
vorher (0006)   approved 45 · archived 38 · followup 31 · idea 128 · in_review 83 · live 141 · planning 110 · withdrawn 80  (656)
                approver: 2 Mitgliedschaften, 2 Gruppen-Zuordnungen · notification 660 · event_status_event 2177 · View 192
Alembic-Log     0007: 0 approved events with an elapsed publish_at become drafts
nachher (0007)  draft 446 · published 141 · archived 69  (656)
                migration-0007-Zeilen: approved/idea/in_review/planning/withdrawn -> draft (45/128/83/110/80),
                live -> published 141, followup -> archived 31 (zusammen 618 = 656 - 38 unveränderte archived)
                approver 0/0, organizer-Mitgliedschaften 4 · notification 38 (comment_added 30, checklist_due 8)
                event_status_event 2795 = 2177 + 618 · View 192 Zeilen
                keine der Spalten submitted_by, approved_by, image_exception, publish_at, published_rev,
                text_reviewed_rev, flyer_checked_at, four_eyes, field_class, trusted; Trigger und Funktionen
                enforce_publish_image, keep_published_poster, exception_ok weg; ck_event_state,
                ck_event_organization, ck_event_tzid vorhanden
```

Dev-DB heute: `draft 636 · published 255 · archived 148`, keine entfernten Spalten. `test_migration_0007.py` (je ein Event
in jedem Altzustand, Rollen, Kinds, View, `image: null`) ist Teil der Vollsuite.

## B: Gates und Läufe

```
backend  ruff check . / ruff format --check .          -> All checks passed / 470 files already formatted
         basedpyright                                   -> 0 errors, 0 warnings, 0 notes
         pytest -m 'not integration and not e2e and not live'  -> 1633 passed
         PROVENANCE_STRICT=1 pytest -m 'not e2e and not live' --cov --cov-branch
                                                        -> 2146 passed (25:20 min), gesamt 97,51 % (Gate 97 %)
         geänderte Tests danach (test_flow, quotes, checklist, comments)  -> 25 passed
         python -m scripts.coverage_critical            -> ok (0 file(s) below 100 %)
         seed_dev (erneut)                              -> 0 neue Zuordnungen, 0 neue Dossiers
         deploy/compose-lint.sh                         -> compose-lint ok
         backup.sh (Dev-Dienste) + restore-smoke.sh     -> restore smoke ok, Revision 0007_event_dossier, 1039 Events, 630 Dateien
frontend npm run lint / npm run typecheck               -> sauber
         npx jest --coverage                            -> 182 Suites, 1482 passed, 1 skipped, 1 todo; 98,52 / 94,77 / 97,44 / 99,1
         npm run build                                  -> Initial total 621,40 kB (161,91 kB übertragen), unter 633,74 kB
e2e      E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m1..m5.spec.ts e2e/m5b.spec.ts  -> 34 passed (5,8 min)
m5b      python -m scripts.m5b_acceptance               -> all checks passed (298 ok; Schemathesis 1402 Fälle, 0 Fehler)
```

## C: Aufräumprobe (Kontrakt 11 k)

```
grep -rlE 'in_review|followup|withdrawn|\bT0[0-9]\b|\bT1[0-2]\b|fourEyes|four_eyes|imageException|image_exception|
  fieldClass|field_class|approver|trusted|/api/tasks|view=board' backend/{app,worker,scripts,tests,seeds} frontend/{src,e2e} deploy
```

39 Dateien, alle begründet: Migrationen `0002` bis `0007` und ihre Tests (`test_migration_0005/0006/0007`); Verlauf und
Altzustände (`events/models.py` `LEGACY_STATES` für den History-CHECK, `revision_views.py` `LEGACY_KEYS` für alte
Revisionen, `test_db_nets.py`); der Modulname `followup` (Router für Outcome und `verify-howto`, Kontrakt 5.1) und die
Checklisten-Phase `followup` (Beschriftung "Nachbereitung", Kontrakt 6); Negativtests, die das Fehlen prüfen
(`approver` abgelehnt, kein `trusted`, kein `imageException`, kein `fieldClass`, die 404 in `m5b_rights.py`); der
Upstream-Golden in `test_hash.py` (`"transition": "T01"`, kopiert aus dem Workflow-Tool, darf sich nicht ändern);
`antiabuse.py` ("trusted proxies") und `calendar-grid.util.ts` (`T00:00:00Z`) sind Wortgleichheit. Verzeichnisse
`modules/pipeline`, `modules/tasks`, `events/board.py`, `features/{pipeline,tasks}`, `dossiers/{transition,exception,assign}`,
`shared/ui/{pipeline-board,guard-list}`, `tests/*/pipeline` gibt es nicht mehr.

## D: Fixes der Integration (eigene Commits)

1. `fix(deploy)`: `dev-up.sh` startet API und Worker mit `Restart=on-failure`. Der Worker beendet sich, wenn Redis weg
   ist; als `--collect`-Unit verschwand er dann, und der Cache-Check (`redis_up` startet `stupa-worker` neu) brach ab.
   Das war auch der Grund, warum `stupa-worker` vor dieser Runde nicht lief.
2. `test`: `m5b_acceptance` deckt jetzt den Kontrakt ab: Doku-Pfad mit Poster per API und ohne Poster mit `hintCount`
   und `no_poster = warn`, Rechte (submitter 403, organizer-makers 404 beim Lesen und Veröffentlichen, editor
   veröffentlicht fremd), entfernte Routen, "Neu aus Vorlage" mit kopierter Anleitung, Format und Bibliothek,
   Kategorie-Umbenennung im Feed (`scripts/m5b_dossier.py`, `scripts/m5b_rights.py`).
3. `test(e2e)`: m3 prüft die gespeicherte Startzeit mit `expect.poll`; "Gespeichert." stand schon vom vorigen Speichern
   da, der direkte Lesezugriff kam zu früh.
4. `chore`: `seed_followup.py` heißt `seed_docs.py` (es füllt die Doku der Seeds, Kontrakt sagte "löschen", der Inhalt
   wird aber gebraucht); veraltete Guard-Docstrings in Checklisten- und Kommentar-Tests, `/api/tasks` im
   Kanarien-Test der Angebote entfernt; `tests/fixtures/movienight.yaml` gelöscht (einziger Leser `m5_fixture.py` war
   schon weg, die Datei trug noch `live` und `followup`).
5. `test`: Integrationstest für `PUBLISH_REQUIRES_EDITOR=true` über HTTP (organizer 403, editor 200).
6. `docs`: Skill `be-lifecycle` ersetzt `be-pipeline`; `be-events`, `be-archive`, `be-auth`, `be-notifications`,
   `be-public`, `conventions`, `CLAUDE.md`, `README.md` auf das Event-Dossier.

## E: Abweichungen vom Kontrakt (zur Nachführung)

- Die alten Abnahmeskripte `m1_acceptance` bis `m5_acceptance`, `m5_clone`, `m5_fixture`, `m5_followup`, `m5_frame`
  hat der Backend-Builder gelöscht statt bereinigt (Kontrakt 5.1 letzte Zeile). Ihre Prüfpunkte, soweit sie noch
  gelten, laufen in `m5b_acceptance` (Login, Rechte, Klon, Suche, Feed, ICS, Kanarienvogel, Schemathesis, Cache);
  die M4-Prüfungen (Anhänge, Scan, Mails) liegen nur noch in den Integrationstests.
- Die Tests aus Kontrakt 9 tragen andere Namen: der Lebenszyklus-Pfad steht in `tests/integration/events/test_flow.py`
  und `test_actions.py`, der Worker in `tests/integration/archive/test_followup.py` (12 h, nicht früher, abgesagte,
  Fehler stoppt nicht).
- `GET /api/events?view=board` antwortet 422 (`validation_error`), nicht 404.
- Review-Rest 25 (Aufräumen der Abnahme-Dossiers) nicht gebaut: `event_status_event` und `event_revision` sind
  append-only, ein SQL-Löschen bräuchte einen Weg am Trigger vorbei. Ein voller Lauf legt etwa 30 Dossiers an (Präfix "M5b"/"M5"), dazu Playwright etwa 30 ("E2E …").
- `EventOut.allowedActions` liest `publish_requires_editor` über `get_settings()` (global), die Route über die
  Abhängigkeit; in Betrieb dieselbe Quelle, im Test mit überschriebenem Setting zeigt `allowedActions` den alten Wert.

## Offen

- Luis: Entscheidungen 13.1 O1 bis O8 (Vorschläge sind gebaut), dazu Review-Reste 15 (`CODEOWNERS`-Team), 16
  (Kalender-Import in Thunderbird, Google, Apple, Schrittfolge `M5-ABNAHME.md` T), 17 (D8), 18 (Kosten für `viewer`,
  = O2), 22 (Pilotkriterium "Dossier anlegen bis Archiv", `pilot_check.py` gegen die Ziel-Instanz), 23 (PLAN §18 Minor 2, 3).
- axe gegen den Produktions-Build hinter nginx (8081) nicht gelaufen, nur gegen `ng serve`.
- Kontrakt 9 nennt die Rolle `stupa`, `viewer`, `member`, `admin` in der Matrix: abgedeckt in `test_lifecycle_matrix.py`
  (rein) und `test_rbac_matrix.py`; im HTTP-Lauf nur viewer, submitter, organizer, organizer-makers, editor.
- Handy: die klebende Filterleiste der Liste braucht drei Zeilen (Hinweis des Frontend-Builders, Design-Review).
- Ein frischer Dev-Keycloak importiert den Realm ohne `approver-*`; ein laufender Container kennt die alten Nutzer noch
  (unschädlich, sie haben keine Zuordnung).
- Zwei OpenAPI-Warnungen "Duplicate Operation ID" für die GET/HEAD-Routen der ICS (bestanden schon vor M5b, nicht behoben).
