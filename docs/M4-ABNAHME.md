# M4-Abnahme: Protokoll vom 19. und 20.10.2026

Lauf auf dem Entwicklungsrechner (NixOS, Docker lokal), Arbeitsbaum auf `feat/m3-pipeline`, nicht committet (der Branch
`feat/m4-dossier` entsteht beim Commit-Schritt). Kein Live-System berührt: IdP ist der lokale Keycloak, alle Daten liegen
in lokalen Containern. Kriterium wörtlich: `docs/M4-KONTRAKT.md` Abschnitt 9.3 (PLAN §16.1, Zeile M4). Die drei Builder
(`backend-dossier`, `backend-mail`, `frontend`) haben ihre Teile geliefert; der Integrationslauf (Abschnitt I) hat alles
erneut ausgeführt, die Verdrahtung korrigiert und die Ergebnisse unten belegt.

## Ergebnis

| Teil des Kriteriums | Ergebnis | Beleg |
|---|---|---|
| EICAR in Quarantäne | erfüllt: vor dem Scan 409 `quarantined`, ClamAV meldet `infected`, Objekt gelöscht (`storage_key` NULL), Download 410 `attachment_infected`; zweite Datei sauber, Download 200 | A (a), `test_attachment_quarantine`, `test_eicar_flow` |
| SVG und `.docm` 415 | erfüllt: SVG mit `<script>` als `other` und als `poster`, `.docm`, `.docx` mit `vbaProject.bin` je 415 `unsupported_media_type` | A (b), `test_mime_attachment_allowlist` |
| Bombenbild abgelehnt | erfüllt: PNG 30 000 × 30 000 (106 KiB) 422 `image_rejected`; Spitzen-RSS (`VmHWM`) von API und Worker +0 MiB | A (c), `test_clean_image_bomb` |
| `€`/Emoji im Dateinamen ohne 500 | erfüllt: `Plakat 5 € 🎬.pdf` und `🎉.png` 201, Name bleibt, Download mit ASCII-Fallback und `filename*=UTF-8''…` | A (d), `test_filename_euro_emoji` |
| Rückfrage am Poster blockiert T04, bis sie gelöst ist | erfüllt: Guard `open_comment_on_hero`, T04 422; Poster ersetzt: weiter 422; nach `resolve` T04 200 | A (e), Playwright m4 "a question on the poster …", `test_t04_blocked_by_open_hero_comment` |
| Checkliste aus Kategorie-Vorlage, Fälligkeiten neu nach Datumsänderung | erfüllt: Kategorie `party` legt 9 Punkte an; `startsAt` +10 Tage: `checklistRecomputed = 7`, alle offenen Vorlagenpunkte +10 Tage, manueller und erledigter Punkt unverändert; offener Pflichtpunkt `planning` blockt T02 mit `checklist_open` | A (f), Playwright m4 "checklist …", `test_checklist_due_after_date_change` |
| Mailvorlage mit Platzhaltern gerendert, unbekannter Platzhalter als Fehler | erfüllt: Betreff und Text mit allen vier Pfaden, Ortszeit `28.11.2026, 22:00 Uhr`; `{{ event.raum }}` 422 `template_invalid` mit `unknown_placeholder`, `allowed` listet die vier Pfade | A (g), Playwright m4 "mail template …" |
| Roundtrip-Korpus byte-gleich (sonst Textarea Standard) | **nicht byte-gleich, Rückfall greift:** 29 von 30 Dateien weichen ab (`roundtrip-gate.json`: `passed: false`), deshalb ist der Quelltext (Textarea mit Vorschau) der Standardmodus, Tiptap per Umschalter "Editor / Quelltext"; im Browser geprüft (Radio "Quelltext" ausgewählt). Backend-Gegenprobe byte-gleich: `test_document_body_stored_verbatim` mit allen 30 Korpusdateien | H, `npm run gate:roundtrip` |
| Vergleichsangebote für fremde Orgs unsichtbar (Test) | erfüllt: `organizer-makers` 404 auf Liste, `select` und Datei; `member` 404 auf Liste und Datei, 403 auf `select` (Routen-Gate, siehe Kontrakt 10.1.21); `viewer-fsi` 403 ohne Betrag; `editor` sieht 123 457 ct; kein Betrag in Dossier, Revisionen, Liste, Feed, Audit | A (i), `test_quotes_cross_org_404`, Playwright m4 "a foreign organization …" |
| Mails gehen nur mit laufendem Redis raus | erfüllt: mit Redis erzeugt T02 eine Mail an die Redaktion, arq-Job `mail:<sha256>` meldet `sent`; Redis angehalten: T02 200, In-App-Zeile da, Mail verworfen, Log `mail dropped, queue error (key=mail:…)` ohne Adresse, kein Job; Redis wieder an, Worker neu gestartet | A (j) |

Zusatzpunkte aus 9.3: Fälligkeitsmail (k) genau eine Mail, zweiter Lauf `mails=0`; Medien-GC (l) in zwei Läufen
(`marked=1`, dann `swept=1`), das Bild der alten Dokumentrevision bleibt und streamt; EXIF (m) weder im Download noch in
der Vorschau, `exiftool -a -G1` auf den Download zeigt nur die Gruppen `ExifTool` und `System`; Handy und Hell/Dunkel (n)
in Playwright (I08 bis I12, I27, I28 bei 360 px ohne seitliches Scrollen, axe grün in beiden Themen, Tastaturpfad für
Upload und Checkliste).

## A: API-Abnahme (`backend/scripts/m4_acceptance.py`)

Gegen den Dev-Stack mit echten OIDC-Logins (`organizer-fsi`, `editor`, `organizer-makers`, `member`, `viewer-fsi`).
SQL liest nur oder stellt die Uhren des Medien-GC (`created_at`, `gc_marked_at`); Worker-Jobs (`send_due_reminders`,
`gc_media`) laufen einmal von Hand auf dem laufenden Worker. Das Skript setzt zu Beginn die stündlichen Upload-Zähler
zurück (`rl_attachments_per_hour = 30`), sonst scheitern Wiederholungsläufe an 429. Gekürzte Ausgabe (20.10.2026):

```
a: EICAR upload -> 201 · download before the scan is 409 · infected · 410 · storage_key NULL · clean download 200
b: bild.svg as other/poster -> 415 · brief.docm -> 415 · brief.docx (vbaProject.bin) -> 415, je unsupported_media_type
c: bomb PNG 30000x30000 (106 KiB) -> 422 image_rejected · stupa-api RSS 174 MiB, peak +0 MiB · stupa-worker peak +0 MiB
d: attachment; filename="Plakat 5 _ _.pdf"; filename*=UTF-8''Plakat%205%20%E2%82%AC%20%F0%9F%8E%AC.pdf
   attachment; filename="_.png"; filename*=UTF-8''%F0%9F%8E%89.png
m: JPEG with GPS -> 201 · no EXIF · preview without EXIF
e: question on the poster -> 201 · guard names it · T04 blocked -> 422 open_comment_on_hero · poster replaced -> 201
   · replacing the poster does not resolve the question · resolve -> 200 · T04 -> 200
f: template party added 9 items · checklistRecomputed = 7 · seven items +10 days · manual unchanged · done unchanged
   · T02 with open required planning items -> 422 checklist_open
g: 'Einladung: M4 Mail …' / 'Hallo,\nM4 Mail … am 28.11.2026, 22:00 Uhr im Kinosaal 9-133.\nFachschaft Informatik'
   unknown placeholder -> 422 template_invalid, reason {code: unknown_placeholder, field: event.raum, line: 1, allowed: [4]}
i: organizer-makers list/select/file -> 404 · member list 404, select 403, file 404 · viewer-fsi 403 (no amount)
   · editor sees the amount · no amount in dossier, revisions, /api/events, feed, audit
j: mail job mail:b14406fca53ebe1… sent by the worker · Redis stopped: T02 200, in-app rows exist
   · WARNING app.mail mail dropped, queue error (key=mail:e788e78a…) · no mail job for the dropped mail (ResultNotFound)
k: send_due_reminders: items=1 mails=1 / send_due_reminders: items=0 mails=0 · one checklist_due row · mail sent
l: gc_media: marked=1 swept=0 unmarked=0 / gc_media: marked=0 swept=1 unmarked=0 · orphan deleted · revision image stays
all checks passed (171 ok)
```

Wiederholung am 20.10.2026, 10:22 Uhr (Abschnitt R): 174 ok, darunter `d` zusätzlich mit `Rechnung €.pdf`
(`filename="Rechnung _.pdf"; filename*=UTF-8''Rechnung%20%E2%82%AC.pdf`), `c` mit +0 MiB Spitze bei API und Worker,
`j` mit `mail dropped, queue error (key=mail:a04fe53d…)` und ohne Job für die verworfene Mail. `exiftool -a -G1` auf den
GPS-Download zeigt nur `Composite`, `ExifTool`, `File`, `JFIF`, `System`: keine EXIF- und keine GPS-Gruppe.

## H: Roundtrip-Gate E20

```
$ npm run gate:roundtrip   -> roundtrip.gate.spec.ts 2 passed; roundtrip-gate.json unverändert
  {passed: false, failed: [29 Dateien, alle außer 16-*], corpusHash: f8360a5455e0f3a7, kitCommit: fad371883675dc4b}
```

`failed`: 01-ablauf-movienight, 02-checkliste-technik, 03-ungeordnet-verschachtelt, 04-geordnet-verschachtelt,
05-tabelle-ausrichtung, 06-links, 07-bild, 08-code, 09-zitat, 10-ueberschriften, 11-hervorhebung, 12-umbrueche,
13-umlaute-emoji, 14-mailvorlage-einladung, 15-mailvorlage-absage, 17-ende-leerzeilen, 18-crlf, 19-anleitung-party,
20-anleitung-ausfahrt, 21-tabelle-einfach, 22-liste-mit-absaetzen, 23-horizontale-linie, 24-inline-gemischt,
25-sonderzeichen, 26-bild-mit-link, 27-aufgaben-verschachtelt, 28-mail-mit-liste, 29-ueberschrift-absatz-code,
30-lange-zeile. Die einzige bestandene Datei endet ohne Zeilenumbruch: der Kit-Serializer verliert den Schluss-Umbruch,
dazu Aufgabenlisten, Ausrichtung und Referenzlinks. Folge laut Kontrakt 7: Textarea ist Standard (Playwright sieht im
Reiter Mails das Radio "Quelltext" ausgewählt).

## B/D: Gates

```
backend  ruff check . / ruff format --check .           -> All checks passed / 400 files already formatted
         basedpyright                                    -> 0 errors, 0 warnings, 0 notes
         alembic heads / current                         -> 0005_dossier_knowledge (head), ein Head, DB auf head
         seed_dev zweimal                                -> 0 neue Zuordnungen, 0 neue Dossiers
         PROVENANCE_STRICT=1 pytest -m 'not e2e and not live' --cov --cov-branch
                                                         -> 2090 passed (15:03 min), gesamt 98 %
         python -m scripts.coverage_critical             -> ok (0 file(s) below 100 %)
         deploy/compose-lint.sh                          -> compose-lint ok
frontend npm run lint / npm run typecheck                -> sauber
         npx jest --coverage                             -> 151 Suites, 1263 passed, 1 skipped, 1 todo;
                                                            98,85 / 94,17 / 97,81 / 99,46
         npm run gate:roundtrip                          -> 2 passed, Entscheidung unverändert (passed: false)
         npm run build                                   -> Initial total 612,95 kB (159,89 kB übertragen)
e2e      E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m1..m4.spec.ts
                                                         -> 23 passed (3,8 min); nach der Korrektur in R m1+m4 10 passed
m1..m3   python -m scripts.m1_acceptance / m2 / m3       -> all checks passed (48 / 75 / 141 ok)
m4       python -m scripts.m4_acceptance                 -> all checks passed (174 ok)
```

## I: Integrationslauf (19. und 20.10.2026)

Aufbau: Dev-Stack nach einem Neustart des Rechners neu gestartet (`docker-compose.dev.yml`, Postgres, Redis, MinIO,
ClamAV, Keycloak healthy). API und Worker als `systemd-run --user`-Units `stupa-api`/`stupa-worker` mit
`EnvironmentFile=backend/.env` (der Worker liest `REDIS_URL` aus der Umgebung, ohne die Datei sucht er `redis:6379`) und
`LD_LIBRARY_PATH` (libstdc++, libmagic); `ng serve :4200` als Unit `stupa-ng`.

```
I1 alembic upgrade head (0004 -> 0005_dossier_knowledge), roles.sql, seed_dev zweimal (0 neue Zeilen)
I2 Verdrahtung geprüft: notify-Aufrufe in pipeline/notices (T02, T03, transition_done), actions_router,
   dossier/comments, dossier/checklist, worker/advance, worker/mail; dispatch_mails nach dem Commit; Router
   notifications/account/dossier/media registriert; WORKER_FUNCTIONS und Crons (send_due_reminders :10,
   gc_notifications 03:40, gc_media 03:50) im laufenden Worker ("Starting worker for 18 functions")
I3 PROVENANCE.backend-dossier.json (1) und PROVENANCE.frontend-m4.json (16) in PROVENANCE.json gemischt, Dateien entfernt
I4 m4_acceptance geschrieben und grün; m1/m2/m3_acceptance grün nach den Anpassungen unten
I5 Playwright m1..m4 gegen ng serve, axe Hell und Dunkel (m3 Board, m4 alle neuen Reiter, Konto, Inbox)
I6 coverage_critical um die fünf M4-Dateien erweitert, Lücken mit Tests geschlossen
```

Korrekturen im Integrationslauf:

- **Mailvorlage vor dem ersten Speichern:** das Frontend ruft `render-preview` mit `docId = new` auf, das Backend
  antwortete 422 (UUID-Pfad). Route nimmt jetzt `new` (ungespeicherter Entwurf) und antwortet bei ungültiger Id 404;
  `test_an_unsaved_template_previews_under_new`. Kontrakt 10.1.22.
- **Kontrast der Glocken-Zähler:** Nav-Rail und Bottom-Bar setzten `color: #fff` auf `--color-danger`; axe meldete im
  dunklen Thema `color-contrast` (serious). Jetzt `--color-on-danger` aus dem Kit.
- **`confirm-flyer` ohne Poster:** der neue Zweig (Bestätigung am Poster) hatte keinen Test, `pipeline` fiel unter 100 %
  Branch. Test `test_confirm_flyer_marks_the_poster_and_works_without_one`.
- **`coverage_critical`** prüft zusätzlich `files/attachments`, `files/mime`, `dossier/comments`, `dossier/checklist`,
  `notifications/service` (Kontrakt 9). Neue Tests `tests/integration/dossier/test_edge_branches.py` (Vorlage je
  Kategorie und `generic`-Rückfall, Punktänderungen, fremde Punkte/Kommentare, Umbenennen, zweimal Ausblenden,
  `rescan` ohne Recht, kaputte Mailvorlage behält die In-App-Zeile) und `tests/unit/test_defensive_branches_m4.py`
  (Datenbank-Netze, Einwilligung, Social-Post ohne Bild, Rechteprüfungen hinter dem Routen-Gate). Toter Code entfernt:
  der leere Entfall-Grund in `_waiver` (der Aufrufer leert vorher) und die Organisationsprüfung in `check_assignee`
  (ohne Organisation findet die Abfrage keine Mitgliedschaft); `retire` nutzt `_flush_or_conflict`.
- **M3-Skripte und -Specs auf M4 nachgezogen:** `m3_acceptance.py` lädt 1400 × 900 hoch (D6, 1200 px) und schreibt
  vor T03 eine Rückfrage (T03 braucht sie jetzt). `e2e/m3.spec.ts` filtert das Board auf den eigenen Titel
  (`/pipeline?q=…`): die Spalten zeigen nur ihre ersten Karten, die Dev-DB hat inzwischen 69 Dossiers in `live`; und
  wartet nach dem Verschieben auf die neu gezeichnete Karte, bevor sie wieder aufgenommen wird.
- **`e2e/m4.spec.ts`** um den Prüfpunkt (n) erweitert: 360 px, fünf Reiter, Konto und Inbox ohne seitliches Scrollen,
  axe in beiden Themen, Checkliste per Leertaste, Upload per Tastatur.
- **Kontrakt erweitert** (10.1.19 bis 10.1.23), `CLAUDE.md` und `README.md` auf M4 nachgeführt.

Weiter laufend: `stupa-api` (:8000), `stupa-worker`, `stupa-ng` (`ng serve :4200`), Dev-Stack-Container. Keine weiteren
Units oder Container. Abbau bei Bedarf: `systemctl --user stop stupa-api stupa-worker stupa-ng`.

## R: Wiederholungslauf (20.10.2026, Integrationsagent)

Alle Gates, Abnahmeskripte und Playwright-Läufe aus B/D erneut ausgeführt, mit den Werten oben. Verdrahtung im Code
nachgesehen: `notify_event`/`notify` in `pipeline/notices` (T02, T03, `transition_done`), `dossier/comments`,
`dossier/checklist`, `worker/mail`; `dispatch_mails` nach dem Commit in `pipeline/router`, `actions_router`,
`comments_router`, `checklist_router`, `worker/advance`; Router `notifications`, `account` und `DOSSIER_ROUTERS` in
`api_routers.py`; `WORKER_FUNCTIONS` und die drei M4-Crons in `worker/main.py`. Die sechs Platzhalter-Guards aus M3 12.18
sind in `pipeline/guards/content.py` und `media.py` echt.

- **Redis-Kriterium gegen den Kontrakt geprüft:** Kontrakt 5.7 und PLAN 9.4 verlangen "ohne erreichbares Redis wird die
  Mail verworfen" (Upstream-Verhalten) mit Warnung im Log ohne Adresse. Eine Outbox oder Fehlerliste gibt es nicht und
  ist nicht verlangt. Sichtbar bleibt die In-App-Zeile in der Inbox, die Aktion selbst gelingt (T02 200).
- **Korrektur `e2e/m4.spec.ts`:** Das Protokoll behauptete, Playwright sehe im Reiter Mails das Radio "Quelltext"
  ausgewählt, die Spec prüfte das aber nicht. Jetzt prüft sie `aria-checked="true"` auf dem Radio "Quelltext" nach
  "Neue Vorlage". `m1.spec.ts` und `m4.spec.ts` mit Prettier formatiert.
- **Hinweis zum Testlauf:** Ein erster pytest-Lauf mit exportierter `backend/.env` ergab 13 Fehlschläge in
  Einstellungs-Tests (OIDC, Speicher, ClamAV, öffentliche DB-URL), weil die Tests die Standardwerte erwarten. Ohne die
  Datei sind sie grün; die Zahlen oben stammen aus dem sauberen Lauf.

## Offene M3-Punkte, die M4 berührt

- Platzhalter-Guards (M3-Kontrakt 12.18) liefern jetzt Daten: `openCommentRequired` zählt offene Wurzelkommentare
  (in Produktion nie mehr `None`), `noOpenCommentOnField(hero)` mit Ersetzungskette, `checklistDone(planning)`,
  `attachmentsScanned`, `rightsComplete` (vier Felder), `flyerDateConfirmed` (Bestätigung am Poster). Weiter
  Platzhalter: Dubletten, `facts`, Nachbereitungsfelder, Standort-Bestätigung, Wandzeit-Warnungen (M5/M6).
- T07 und `public_status`, Konfliktdialog, No-op-PATCH: unverändert offen (Entscheidung Luis).

## Offen

- **Roundtrip-Gate nicht bestanden** (29/30): Luis entscheidet, ob der Tiptap-Serializer nachgebessert wird
  (Schluss-Umbruch, Aufgabenlisten, Tabellen-Ausrichtung, Referenzlinks) oder ob der Quelltext Standard bleibt.
- Entscheidungen D1 bis D7 (Kontrakt 10.2), dazu: Poster-Mindestgröße als Sperre (D6, Konstante `MIN_POSTER_EDGE`);
  `social_post` braucht `meta.channel`; Mitgliederprüfung über die Projektion `membership` (Empfängerliste, keine
  Rechteentscheidung); Anker-Feldnamen akzeptieren Schlüssel und Wire-Namen.
- Statustexte der Anhangsliste weichen vom Kontrakt 3.3 ab ("Geprüft", "Abgelehnt: Schadsoftware gefunden",
  "Prüfung fehlgeschlagen" statt "Sauber", "Infiziert", "In Quarantäne").
- Frontend-Stubs: `facts.budgetCents`, Mitglieder-Endpunkt für die Zuständigen-Auswahl (kein Kontrakt-Endpunkt),
  "Als Vorlage für das Format speichern" ausgeblendet, Rückfrage auf dem Handy inline statt als Sheet.
- `changes_requested` trägt `count` in den Parametern, die Mailvorlage nutzt ihn nicht.
- axe lief gegen `ng serve` (Dev-Build); der Produktions-Build hinter nginx wurde in M4 nicht erneut geprüft
  (Image wie M3 I5).
- `notification` hat keinen Unveränderlichkeits-Trigger; `DELETE` für `events_app` braucht `gc_notifications`.
- Nichts committet. Der Branch `feat/m4-dossier` mit gescopten Commits entsteht im letzten Schritt.
