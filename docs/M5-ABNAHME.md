# M5-Abnahme: Protokoll vom 20.10.2026

Lauf auf dem Entwicklungsrechner (NixOS, Docker lokal), Arbeitsbaum auf `feat/m4-dossier`, nicht committet (der Branch
`feat/m5-archiv` entsteht beim Commit-Schritt). Kein Live-System berührt: IdP ist der lokale Keycloak, alle Daten liegen
in lokalen Containern. Kriterium wörtlich: `docs/M5-KONTRAKT.md` Abschnitt 12.3 (PLAN §16.1, Zeile M5) und 12.4
(Meilenstein A-I, technischer Teil). Die Builder `backend-m5` und `frontend-m5` haben ihre Teile geliefert; der
Integrationslauf (Abschnitt I) hat `scripts/m5_acceptance.py` geschrieben, alles erneut ausgeführt, die Verdrahtung
korrigiert und die Ergebnisse unten belegt. "Erfüllt" heißt in diesem Protokoll: im Lauf gesehen. Was nur vertraglich
zugesagt oder nur von Hand prüfbar ist, steht unter "Offen".

## Ergebnis

| Teil des Kriteriums | Ergebnis | Beleg |
|---|---|---|
| Movienight-Fixture: aus archivierter Ausgabe entsteht ein Dossier ohne Poster, Ausnahme und Angebote | erfüllt: 23 Kopien (8 archiviert, 8 Nachbereitung, 7 live), die volle Ausgabe trägt Poster, `image_exception`, zwei Angebotsgruppen, Kommentar, Checkliste mit Zuständigen, Anleitung, Notiz, Mailvorlage, Rückblick, Ergebnis 87 / 245,00 € / 130,00 €; Klon durch `organizer-fsi` in `idea` mit `derivedFromId`, `poster` und `imageException` leer, Angebote, Anhänge, Kommentare leer | A (a) |
| Checkliste neu gerechnet | erfüllt: 6 Punkte offen, ohne Zuständige, `checklistRecomputed = 6`; Stichproben −28 / −7 / +7 Tage je 09:00 Ortszeit ab neuem Beginn | A (a) |
| "Letztes Mal" zeigt Besucher:innen und Kosten | erfüllt: FSI sieht 87 und 24 500 ct (`restricted = false`); MAKERS sieht 87 ohne Kosten und Erlös (`restricted = true`), nur `shared`-Dokumente kopiert, Angebots-Panel 404, fremde `live`-Ausgabe 404 | A (a) |
| Archivsuche besteht die 20 Mustersuchen ("Fachschaftssitzung" findet "Sitzung") | erfüllt: 20 von 20, je Zeile Soll gleich Ist auf dem Korpus, `total` gleich der durchgeblätterten Treffer; zusätzlich Playwright "Fachschaftssitzung" mit Hervorhebung | A (b), `test_search_20`, Playwright m5 |
| ICS-Golden-Tests grün | erfüllt: 8 Golden-Dateien byte-gleich (`test_ics.py` 35 passed), alle mit `icalendar` und mit ical.js (Parser von Thunderbird) lesbar, RFC-5545-Regeln sauber | A (c), C |
| ICS in Google, Apple, Thunderbird importiert | **nicht geprüft** (manuell, Schrittfolge in Abschnitt T); maschinell geprüft: Absage `STATUS:CANCELLED`, Verschiebung `SEQUENCE` 1 → 2 und `STATUS:TENTATIVE`, UIDs stabil, 25.10.2026 02:30 beide Durchläufe korrekt in ical.js | A (c), C, T |
| Kanarienvogel findet in JSON, ICS nichts Internes | erfüllt: anonym Feed (alle Seiten, Sonderparameter, jede Kategorie), jede ICS, geschlossene Routen sauber; `member`, `organizer-makers`, `submitter-ekhg` je 41 Antworten sauber; `viewer-fsi` ohne Angebotsstrings; Positiv-Kanarienvogel in Feed und ICS gefunden; Gegenprobe der eigenen Organisation findet ihre `org`-Strings | A (d), `test_canary.py` |
| Schemathesis gegen Feed grün | erfüllt: 801 Fälle gegen die laufende Dev-API (`/api/public/*`, `/ics/*`, positiv und negativ, 200 je Modus), 0 Fehlschläge, Feed gegen `feed-v2.json`; dazu `test_schemathesis` in der Integrationssuite | A (e), B |
| Meilenstein A-I: `restore-smoke` grün | erfüllt lokal: `backup.sh` gegen den Dev-Stack (Revision `0006_archive_feed`, 27 Tabellen, 414 Anhangsdateien), `restore-smoke.sh` in einem Wegwerf-Container: "restore smoke ok"; CI-Job `restore-smoke` vorhanden, lief mangels Push nicht | M |

Zusatzpunkte aus 12.3: Feed-Cache (f), Nachbereitung mit gesetzter Uhr (g), Kalender (h), Archiv-Lesen und Bibliothek
(i), Ort und Rahmen (j), Sequenz PLAN 4.6 (k) erfüllt laut Abschnitt A; Browser (l) in Playwright m5 (8 Tests, 360 px und
Desktop, Hell und Dunkel, axe, Tastaturpfade für Palette, Kalender und Klon); Backup und Restore (m) in Abschnitt M.

## A: API-Abnahme (`backend/scripts/m5_acceptance.py`)

Gegen den Dev-Stack mit echten OIDC-Logins (`organizer-fsi`, `editor`, `organizer-makers`, `member`, `viewer-fsi`,
`submitter-ekhg`). Das Skript baut zuerst den Bestand aus `tests/fixtures/movienight.yaml` über die API
(`scripts/m5_fixture.py`); die Uhr bewegt nur SQL auf den Datumsspalten, die Zustände ändern Worker und API. Für die
Nachbereitung (g) setzt es zusätzlich das `at` des Eintritts in `followup` zurück, in einer Superuser-Transaktion mit
abgeschaltetem Append-only-Trigger nur für dieses eine `UPDATE` (ein Job mit verschobenem `now` hätte jedes Dev-Dossier
bewegt). Die Suche (b) legt den synthetischen Korpus einmal per SQL an (`created_by = 'm5-corpus'`), der Kanarienvogel
(d) hängt die internen Strings per SQL an ein Live-Dossier und eine archivierte Kopie des Bestands. Dateien:
`m5_acceptance.py` (Ablauf, `--reuse`, `--only=`), `m5_fixture.py`, `m5_clone.py`, `m5_search.py`, `m5_public.py`,
`m5_canary.py`, `m5_icsrules.py`, `m5_schemathesis.py`, `m5_followup.py`, `m5_frame.py`, `m5_live.py`.
Letzter Lauf 20.10.2026, 15:09 Uhr: **all checks passed (654 ok)**, davon 208 für den Bestand. Gekürzt:

```
a: checklistRecomputed = 6 · 'Plakat bestellen' due 2026-11-06T08:00Z (-28) · 'Technik bestätigen' 2026-11-27 (-7)
   · 'Abrechnung' 2026-12-11 (+7) · notes und mail_template Revision 1 · howto als Link · Vorschau gleich Bericht
   · last time 87 / 245,00 EUR (FSI) · MAKERS: 87 ohne Kosten, restricted, nur mail_template, Panel 404, live 404
   report: title/summary/description/costText/category/format/venue copy · venueText/facts reset · documents copy 2
           · howto link · checklist copy 6 · poster/imageException/files/socialPosts/links/history never · shared link
b01 'Fachschaftssitzung' -> Sitzung FSI, STUPA-Sitzung, Sommerfest der Fachschaft      (außerhalb des Korpus: 12)
b02 'movienight' -> 5, 'Movienight: Whiplash' zuerst   b03 'Movienight Halloween' -> 1   b04/b05 Hüttencafe/Huettencafe -> 1
b06 Praesidium -> 1   b07 Weissbier -> 1   b08 Kinoabnd -> 1   b09 Parti (makers) -> 2   b10 LAN Partie -> 2
b11 Skiausfart -> 1   b12 game togther -> 1   b13 Popcornmaschine -> 1 (über die Anleitung)   b14 Technikverleih (documents) -> 1
b15 Sitzung org=fsi -> 1   b16 Movienight year=2025 -> 2   b17 Movienight state=archived (makers) -> 3
b18 '100%' -> 0   b19 'Kontext-Notiz' (makers) -> 0   b20 'x' -> 0
c: Golden + Writer 35 passed · 8 Golden-Dateien parsen und bestehen die Regeln · all.ics und k/kino.ics: text/calendar,
   kein Cookie, Regeln sauber · cancel -> STATUS:CANCELLED, SEQUENCE steigt · postpone -> SEQUENCE 2, DTSTART folgt,
   TENTATIVE · UIDs stabil · 02:30 zweites Mal DTSTART:20261025T013000Z, erstes Mal DTSTART:20261025T003000Z
   · all.ics 173 Termine, kino.ics 157
d: anonym sauber, Positiv-Kanarienvogel gefunden · member / organizer-makers / submitter-ekhg je 41 Antworten sauber
   · viewer-fsi 31 Antworten ohne Angebotsstrings · Gegenprobe organizer-fsi: eigenes org-Dokument und Kosten gefunden
e: Schemathesis 801 Fälle, 0 Fehlschläge
f: 304 mit aktuellem ETag · T05: Feed-Version 590 -> 591, neuer ETag, alter ETag 200 · Cursor läuft alle 224 Einträge
   genau einmal in Reihenfolge · since -> 1 Eintrag · since mit rohem '+' -> 400 · Feed antwortet aus Snapshot 591
   · Redis angehalten: Feed, all.ics, k/kino.ics 200 aus der View · Redis an: Snapshot kehrt zurück
g: T08 nach Ende + 13 h, bei + 11 h bleibt live · Erinnerung: Aufwärmlauf events=0, dann events=1 mails=1, zweiter Lauf
   mails=0, Mail 'sent' · T09 422 [retrospective_missing, outcome_missing, howto_unverified] · nach Eingabe T09 200,
   format.last_verified_at und Master-Anleitung datiert · zweites Dossier: T09b nach 31 Tagen (archived=1),
   'Anleitung ungeprüft', Format unberührt, auto_archived-Mail 'sent' · verify-howto in archived löst das Kennzeichen
   und datiert das Format · T10 öffnet die Nachbereitung wieder
h: Oktober-Ansicht 28.09.–08.11. (Randtage) 164 Einträge · mehrtägig bis 01.11. · ganztägig · Halloween-Doppel 31.10.
   (19:00 und 21:30) · 100 Tage 200, 101 Tage 422 range_too_large · MAKERS sieht die FSI-Dossiers nicht, editor schon
i: member liest das archivierte Dossier: nur shared-Dokument, nur die saubere shared-Datei gelistet · Download shared 200,
   org 404, pending 404 (nicht gelistet) · Bibliothek ohne org- und pending-Dateien · adopt durch MAKERS kopiert nur den
   Text, keine Datei · member darf nicht übernehmen (403)
j: T04 mit freiem Ortstext 422 location_unconfirmed · confirm-location, T04, T05, Feed zeigt den Ort · Party ohne
   ageLimit blockt T02 (facts_invalid), mit ageLimit 18 nicht mehr · ganztägig: Feed startsOn/endsOn 2026-12-03,
   ICS DTSTART;VALUE=DATE
k: Suche "Whiplash" -> Vorlagenliste -> Klon -> Poster -> T01 -> Planungspunkte erledigt -> T02 -> Rückfrage am Poster,
   T03 -> Poster ersetzt -> T02 -> Rückfrage gelöst -> Ort bestätigt -> T04 -> T05 -> im Feed mit Poster und in all.ics
```

## B: Gates

```
backend  ruff check . / ruff format --check .           -> All checks passed / 525 files already formatted
         basedpyright                                    -> 0 errors, 0 warnings, 0 notes
         alembic heads / current                         -> 0006_archive_feed (head), ein Head, DB auf head
         seed_dev (erneut)                               -> 0 neue Zuordnungen, 0 neue Dossiers
         PROVENANCE_STRICT=1 pytest -m 'not e2e and not live' --cov --cov-branch
                                                         -> 2515 passed, 1 failed (24:42 min), gesamt 97,99 % (Gate 97 %);
                                                            der Fehlschlag ist korrigiert (Abschnitt I),
                                                            danach tests/integration/search 35 passed
         python -m scripts.coverage_critical             -> ok (0 file(s) below 100 %)
         deploy/compose-lint.sh                          -> compose-lint ok
frontend npm run lint / npm run typecheck                -> sauber
         npx jest --coverage                             -> 199 Suites, 1630 passed, 1 skipped, 1 todo;
                                                            98,81 / 94,99 / 97,59 / 99,34 (Schwellen 97/94/97/98)
         npm run build                                   -> Initial total 633,74 kB (164,84 kB übertragen)
e2e      E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m5.spec.ts       -> 8 passed (1,1 min)
         ... e2e/m1.spec.ts e2e/m2.spec.ts e2e/m3.spec.ts e2e/m4.spec.ts            -> 23 passed (3,9 min)
m1..m4   python -m scripts.m1_acceptance / m2 / m3 / m4  -> all checks passed (48 / 76 / 141 / 174 ok)
m5       python -m scripts.m5_acceptance                 -> all checks passed (654 ok)
```

## C: Kalender-Clients ohne Gerät (Thunderbird-Parser)

Thunderbird ist im Profil vorhanden, ein Import dort hätte aber Luis' eigenes Kalenderprofil berührt. Stattdessen liest
ical.js 2.2.1 (die Bibliothek, mit der Thunderbird ICS parst, in einem Wegwerf-Verzeichnis unter `/tmp` installiert) die
Dev-Kalender und die Golden-Dateien und gibt aus, was ein Client sähe; dazu `icalendar` und die Regeln aus
`scripts/m5_icsrules.py` (CRLF, Faltung bei 75 Oktetten, Pflichtfelder, eindeutige UIDs, `VTIMEZONE` je `TZID`, Ende nach
Beginn, keine Steuerzeichen, kein `ORGANIZER`/`ATTENDEE`/`VALARM`/`ATTACH`/`GEO`).

```
all.ics      {"events":162,"status":{"CONFIRMED":156,"CANCELLED":4,"TENTATIVE":2},"allDay":2,"endNotAfterStart":0,
              "dst":["M5 Umstellung erste -> 2026-10-25T00:30:00.000Z","M5 Umstellung zweite -> 2026-10-25T01:30:00.000Z"]}
k/kino.ics   {"events":146, ... gleiche Umstellung}
dst-2026-10-25.ics  Sommerzeit -> 00:30Z, Winterzeit -> 01:30Z;  übrige Golden-Dateien: Status und Ganztägigkeit wie erwartet
```

Befund vor der Korrektur: ical.js las `DTSTART;TZID=Europe/Berlin:20261025T023000` (erstes 02:30, gemeint 00:30Z) als
01:30Z, also als den zweiten Durchlauf. D8 hatte das Gegenteil angenommen. Korrektur siehe Abschnitt I.

## T: Manuelle Abnahme Google, Apple, Thunderbird (offen, für Luis)

Nicht geprüft; die Zeile bleibt unvollständig, bis Luis sie bestätigt (Kontrakt 12.3 c, D16). Schrittfolge:

1. Dev-Stack, API und Worker laufen; `uv run python -m scripts.m5_acceptance --reuse --only=c` erzeugt Absage,
   Verschiebung und die beiden Termine der Umstellung. Datei holen: `curl -o stupa.ics http://localhost:8000/ics/all.ics`
   (die Dev-Umgebung hat kein nginx auf 8081; dort wäre es `http://localhost:8081/ics/all.ics`).
2. **Thunderbird** mit einem frischen Profil (`thunderbird -P`, Profil "stupa-abnahme"), Kalender "Lokal": Datei,
   Importieren, `stupa.ics`. Dann Neuer Kalender, Im Netzwerk, `http://localhost:8000/ics/k/kino.ics`. Prüfen und als
   Bildschirmfoto ohne personenbezogene Daten festhalten: Termine erscheinen; "M5 ICS Absage …" durchgestrichen oder
   als abgesagt; "M5 ICS Verschiebung …" am neuen Datum, vorläufig; "M5 Umstellung erste …" 02:30 Sommerzeit und
   "M5 Umstellung zweite …" 02:30 Winterzeit am 25.10.2026 als zwei verschiedene Zeitpunkte eine Stunde auseinander.
3. **Google Kalender** (Web): Einstellungen, Importieren, `stupa.ics` in einen Testkalender. Dieselben Punkte. Ein Abo per
   URL braucht eine öffentliche HTTPS-Adresse und ist erst auf der Zielinstanz prüfbar.
4. **Apple Kalender** (iPhone oder macOS): Kalenderabo mit der HTTPS-Abo-URL der Zielinstanz
   (`webcal://…/ics/all.ics`); lokal nur Datei-Import per AirDrop oder Mail. Dieselben Punkte.

## M: Backup und Restore (Meilenstein A-I)

```
$ COMPOSE_FILE=docker-compose.dev.yml ENV_FILE=.env.dev BACKUP_DIR=/tmp/m5-backups deploy/backup.sh
  backup /tmp/m5-backups/20261020T123657Z   (db.dump.age 1,2 MB, manifest.json: alembicRevision 0006_archive_feed,
                                             27 Tabellen, event 656, format 7, 414 Anhangsdateien)
$ BACKUP_DIR=/tmp/m5-backups AGE_IDENTITY=secrets/backup-age.key deploy/restore-smoke.sh
  restore smoke ok (/tmp/m5-backups/20261020T123657Z)   # Wegwerf-Container, Revision und Zeilenzahlen gleich, danach entfernt
```

`age` und `jq` kamen über `nix shell nixpkgs#age nixpkgs#jq`. Der CI-Job `restore-smoke` (`.github/workflows/ci.yml`,
`.github/scripts/make-test-backup.sh`) ist geschrieben, lief aber nicht, weil nichts gepusht ist.

## I: Integrationslauf (20.10.2026)

Aufbau: Dev-Stack (`docker-compose.dev.yml`, Postgres, Redis, MinIO, ClamAV, Keycloak healthy), DB bereits auf
`0006_archive_feed` (ein Head). API, Worker und `ng serve` als die bestehenden `systemd-run --user`-Units
`stupa-api`/`stupa-worker`/`stupa-ng`, mehrfach neu gestartet. Worker: "Starting worker for 24 functions" mit
`send_followup_reminders` (:20) und `rebuild_public_cache` (:05, `keep_result=0`).

```
I1 Verdrahtung geprüft: Router location, facts, followup, search, formats, archive, library in api_routers.py; ICS-Router
   in main.py außerhalb von /api; Middleware und nginx kennen /ics/ (ev_ics_redacted für /ics/p/); Worker-Funktionen
   und Crons; Cache-Auslöser über invalidate_feed_cache
I2 PROVENANCE.backend-m5.json (1 Eintrag, ics/writer.py) in PROVENANCE.json gemischt, Datei entfernt
I3 m5_acceptance geschrieben und grün; m1..m4_acceptance und Playwright m1..m4 auf M5 nachgezogen und grün
I4 Playwright m5 zum ersten Mal gelaufen, Fehler unten behoben
I5 drei verwaiste Testcontainer früherer Builder-Läufe (postgres:16-alpine, Ryuk ist abgeschaltet) entfernt
```

Korrekturen im Integrationslauf:

- **Suche, Titel abgeschnitten:** `ts_headline` mit `MaxWords/MinWords` schnitt Titel ab ("STUPA Movienight: Metropolis
  (OmU)" kam als "STUPA Movienight: Metropolis"), und das Frontend zeigt den Titel aus den Segmenten. Der Titel läuft jetzt
  mit `HighlightAll=true` (`search/segments.py: TITLE_HEADLINE_OPTIONS`, `search/query.py`);
  `test_the_title_highlight_keeps_the_whole_title`. Folge: Markup im Titel bleibt als Text in den Segmenten (vorher
  schluckte `ts_headline` es); das Frontend rendert Segmente nur als Text. `test_hits_carry_highlight_segments_and_never_html`
  prüft jetzt "ganzer Titel als Text, Treffer nur 'Whiplash'" (war der eine Fehlschlag des vollen Laufs).
- **ICS, wiederholte Stunde:** Befund aus C. `timezone.ambiguous_instant` ersetzt `fold_instant`: beide Durchläufe der
  wiederholten Stunde gehen als UTC hinaus; Golden `dst-2026-10-25.ics` und `test_the_repeated_hour…` nachgezogen;
  Kontrakt 8.2, 13.1.18 und D8 ergänzt.
- **Hervorhebung bei Komposita (Frontend):** Treffer nur über Trigramm tragen keine Server-Hervorhebung; `highlightTerms`
  markierte nur die wörtliche Eingabe, bei "Fachschaftssitzung" also nichts. Jetzt markiert es auch Titelwörter ab fünf
  Buchstaben, die in einem Suchwort stecken ("Sitzung", "Fachschaft"), akzent- und großschreibungsfrei; zwei Specs.
- **Kontrast im Kalender:** axe meldete `color-contrast` (serious) für `app-status-text.st--muted` auf den Einträgen
  (Fläche 3); dieselbe Regel wie `.rowgroup--bg3` in `styles.scss` jetzt in `calendar-entry.component.scss`.
- **Kalender, Tastatur-Wettlauf:** der Fokus wanderte erst nach `setTimeout`; ein schneller zweiter Pfeil ging vom alten
  Tag aus (Pfeil rechts, Pfeil links landete zwei Tage weiter links). Innerhalb des Rasters fokussiert `moveFocus` jetzt
  sofort, nur beim Monatswechsel nach dem Rendern; Spec "moves the focus at once …".
- **Palette, alte Suche:** die 200-ms-Verzögerung lief nach dem Schließen weiter, beim nächsten Öffnen erschienen Treffer
  der alten Eingabe bei leerem Feld. Öffnen löscht jetzt Zeitgeber und laufende Anfragen; Spec "drops a search …".
- **`e2e/m5.spec.ts`:** `isVisible({timeout})` wartet nicht (der Klon-Test übersprang sich immer), Strg+K vor dem Start der
  App ging verloren, die Monatsschleife des Kalenders klickte zu oft, `name: 'Mehr'` traf "Mehrtägig"-Einträge.
- **`e2e/m1..m4` und `support/dossier.ts`:** `Speichern`/`Bestätigen` exakt (M5 bringt "Rahmen speichern" und "Ort
  bestätigen"), `confirmLocation` über die API vor "Freigeben" (Kontrakt 13.1.15), Feed mit `limit=500`.
- **`m1/m3/m4_acceptance`:** der Feed hat in der Dev-DB mehr als eine Seite; `acceptance_common.feed_pages/feed_items`
  laufen den Cursor ab.
- **`m5_fixture.py`:** das Halloween-Doppel liegt auf dem kommenden 31.10. (19:00 und 21:30 Ortszeit, vorher "heute + 12
  Tage"); die volle Ausgabe trägt Poster **und** `image_exception`; die Mailvorlage ist `shared` (sonst kopiert ein fremder
  Klon nichts); jede archivierte Kopie wird vor T09 geprüft, weil das Format eine Master-Anleitung hat (D5 "nichts zu
  prüfen" greift dann nicht).
- `CLAUDE.md`: Abnahmebefehl `m5_acceptance` mit `--reuse` und `--only`.

Weiter laufend: `stupa-api` (:8000), `stupa-worker`, `stupa-ng` (`ng serve :4200`), Dev-Stack-Container. Keine weiteren
Units oder Container. Die Dev-DB wächst je Lauf von `m5_acceptance` um rund 60 Dossiers (Bestand, Klone, Testdossiers).
Abbau bei Bedarf: `systemctl --user stop stupa-api stupa-worker stupa-ng`.

## Offene M4-Punkte, die M5 berührt

- Platzhalter jetzt echt: `facts` (Profil-Prüfung, Party ohne `ageLimit` blockt T02, Beleg j), Standort-Bestätigung
  (`location_unconfirmed`, Beleg j), Nachbereitungsfelder (`retrospective_missing`, `outcome_missing`,
  `howto_unverified`, Beleg g). Weiter Platzhalter: Dubletten, Wandzeit-Warnungen (M6).
- Frontend-Stubs verdrahtet: `PUT /api/events/{id}/facts` (Rahmen-Feld, "Rahmen speichern"), "Als Format speichern" aus
  der Palette (Playwright m5 Test 8).
- Statustexte der Anhangsliste unverändert ("Geprüft", "Abgelehnt: Schadsoftware gefunden", "Prüfung fehlgeschlagen").
- Roundtrip-Gate (29/30) unverändert: Rückblick und Master-Anleitung nutzen den Quelltext (D17).

## R: Review-Runde (20.10.2026)

Behoben: Cache-Invalidierung bei Änderung von Ort, Organisation und Kategorie im Admin (`invalidate_feed` in
`admin/patching.py`); Zurücksetzen auf eine Revision rechnet abgeleitete Werte (Ortsgenauigkeit, Rahmen, Ganztagstage) wie
`PATCH` und lehnt einen Wechsel der Ganztägigkeit mit `revert_allday_changed` ab; Palette zeigt "Neues Dossier" und "Aus
Vorlage" nur mit `event.create`, "Als Format speichern" nur mit `allowedActions` des offenen Dossiers, Strg+K nur im
Rahmen mit Seitenleiste, aktive Option scrollt in Sicht, Suchfehler und 429 haben einen eigenen Text; T09 und
"Anleitung geprüft" datieren nur das Format der eigenen Organisation; Erinnerungsmail ohne Rest ("nur noch Abschließen");
Redis-Claim der Erinnerung erst nach dem Commit; ICS schreibt jeden Zeitpunkt in `Europe/Berlin`; `HEAD` auf Feed und
ICS; Feed-Filter ohne Steuerzeichen (422 statt 500); Kanarienvogel um Format-Beschreibung, Standardwerte und
Master-Anleitung erweitert (Betrag jetzt 11-stellig, Treffer nur zwischen Nicht-Hex-Zeichen); fremde Vorlage setzt auch
`priceText`, `meetingPoint`, `protocolOwner` zurück und entfernt Bildverweise aus der Beschreibung; Klon-Dialog fragt bei
ganztägiger Vorlage keine Uhrzeit (`TemplateCard.allDay`) und bietet nur Organisationen mit `event.create`.

Nicht umgesetzt: Prüfergebnis eines Posters bewegt den Feed nicht, denn ein Trigger verbietet jede Änderung am Poster eines
veröffentlichten Dossiers (`CheckViolation`), der Fall tritt nicht auf. Negativ-Cache für unbekannte ICS-Slugs bleibt
beim nginx-`limit_req`. Audit-Zeilen im Kanarienvogel nicht erweitert.

## Offen

- **Import in Thunderbird, Google, Apple nicht geprüft** (Abschnitt T); nur Parser und Regeln sind belegt.
- **D8 erweitert ohne Luis' Okay:** beide Durchläufe der wiederholten Stunde in UTC (Abschnitt I). Rücknahme wäre eine
  Zeile in `timezone.py` plus Golden.
- **`viewer-fsi` sieht Ergebniskosten der eigenen Organisation** (Formatseite, "Letztes Mal"), aber keine Angebote. Der
  Kontrakt nennt im Kanarienvogel "viewer" ohne Organisation; der Integrationstest nimmt einen fremden Viewer
  (`viewer-tec`), den der Dev-IdP nicht hat. Entscheidung für Luis, ob Viewer Kosten sehen.
- `pending`-Anhang eines fremden Dossiers antwortet 404 (nicht gelistet) statt 409 (Kontrakt 12.3 i nennt 409).
- Movienight-Bestand synthetisch (D15): nur Zahlen 23/8/8/7, Wochentagsmuster und Titelmuster aus KARTE 2.7; das
  Semesterposter ist je Dossier eine eigene Datei mit gleichem Inhalt, nicht ein Bild an sieben Dossiers.
- Die 20 Mustersuchen laufen auf der Dev-DB gegen den Korpus; Treffer außerhalb des Korpus werden gezählt, nicht bewertet.
- Pilot-Kriterien (eine echte Veranstaltung Idee bis Archiv, 10 echte Events mit Bild, Feedback als Issues) sind aus dem
  Repo nicht prüfbar; geliefert sind `scripts/pilot_check.py` (nicht gelaufen, braucht die Zielinstanz) und die
  Issue-Vorlage. `.github/CODEOWNERS` hat einen Platzhalter-Owner (`TODO(owner)`): bis das echte GitHub-Handle eingetragen und "Require review from Code Owners" auf `main` aktiv ist, schützt E39 keine Prüfung. Vor dem Pilot-Tag erledigen.
- PLAN §18 Minor 2 (Abo-Antwortzeit, B3) und Minor 3 (Mitveranstalter, D12) bleiben offen.
- Initiales Bundle wuchs um 20,8 kB (612,95 → 633,74 kB); der Kontrakt wollte kein Wachstum, Gate ist nur das
  Angular-Budget. Die Kontrakt-Abweichungen des Frontend-Builders (eigene Klon-Vorschau statt `app-config-diff`,
  Leseseite `/archiv/:id`, "Dossiers" im "Mehr"-Sheet, keine Format-Stammdatenpflege in der UI) sind unverändert.
- axe lief gegen `ng serve` (Dev-Build), nicht gegen den Produktions-Build hinter nginx.
- Nichts committet, nichts gepusht. Der Branch `feat/m5-archiv` mit gescopten Commits entsteht im letzten Schritt.
