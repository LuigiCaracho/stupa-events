# Abnahme B3: Get started, Abos, Listmonk (mit dem Token-Teil von B2)

Stand 2026-10-24, Branch `feat/b3-abos` (von `feat/b1-public` @ `543433d`), nichts gepusht. Grundlage:
`docs/B3-KONTRAKT.md` Abschnitt 10 (Wortlaut PLAN 16.2). Alles lief lokal: Dev-Dienste aus
`deploy/docker-compose.dev.yml` (neu: `listmonk` v5.1.0 mit eigener `listmonk-db`, `mailpit` v1.31.2 auf SMTP 1026 und
UI/API 8025), API und Worker als User-Units (`stupa-api`, `stupa-worker`), `ng serve` auf 4200, Keycloak 8090. Für die
nginx-Prüfungen lief die Produktionskonfiguration `deploy/web/nginx.conf` als Wegwerf-Container vor der Host-API
(`scripts/b3_ops.nginx_up`, Port 8082, danach entfernt). Kein Live-System berührt.

**Aufbau der Dev-Umgebung.** `backend/.env` darf hier nicht gelesen werden (Zugriffsregel). Die B3-Schlüssel
(`SUBS_DATABASE_URL`, `PGCRYPTO_EMAIL_KEY`, `EMAIL_HASH_KEY`, `ALTCHA_HMAC_SECRET`, `LISTMONK_*`, SMTP auf Mailpit) liegen
deshalb in der neuen, gitignorierten Überlagerung `backend/dev.env.local`. `deploy/dev-up.sh` liest sie nach
`backend/.env` (Fix E3), und das Listmonk-Seed schreibt seinen Token dorthin. Die Schlüssel sind frisch erzeugt.
`dev-up.sh` hat den Postgres-Container einmal neu erstellt (wegen `EVENTS_SUBS_PASSWORD`) und die Rolle `events_subs`
angelegt. Danach liefen `alembic upgrade head` (0008 → 0009) und die Listen-Synchronisierung (62 Listen).

## Ergebnis

B3 ist **technisch erfüllt**. Das **Gate B3 ist offen**, weil die schriftliche Rückmeldung der
Datenschutzbeauftragten fehlt (dokumentiert in `docs/B3-DATENSCHUTZ.md`, blockiert nicht). Der Token-Teil von B2
ist erfüllt.

| # | Prüfpunkt (Kontrakt 10) | Ergebnis | Beleg |
|---|---|---|---|
| a | Token nur als Hash in der DB, nie im Log | erfüllt nach Fix E7 | B (i), Integration `test_profile_ics`, Kanarienvogel |
| b | Rotation invalidiert; unbekannt und widerrufen: dieselbe 404 | erfüllt | B (d, h), `test_profile_ics` |
| c | "nur Partys, keine Sitzungen" → Profil, ICS, passende Listen | erfüllt | B (a), Playwright 1 |
| d | GET auf Bestätigungslink bestätigt nicht | erfüllt | B (b), Playwright 3 |
| e | gleiche Antwort für bekannte und unbekannte Adressen (Minor 2) | erfüllt, Differenz der Mediane unter 1 ms | B (c), Playwright 4 |
| f | Listmonk-down verliert nichts | erfüllt | B (e) |
| g | Abmeldung bleibt nach Abgleich | erfüllt nach Fix E2 | B (g) |
| h | Digest liegt als Entwurf | erfüllt | B (f) |
| i | Löschen entfernt Adresse, Profil, Token, Listmonk-Datensatz | erfüllt | B (h), Playwright 3 |
| j | Limits, ALTCHA, Löschjobs | erfüllt (Integration) | `test_limits_int`, `test_privacy`, `test_worker_jobs` |
| k | `events_subs` hat nur die vorgesehenen Rechte | erfüllt (Integration) | `test_db_grants_roles_sql`, `test_param_log` |
| l | Gate B3 dokumentiert | dokumentiert, Rückmeldung **offen** | `docs/B3-DATENSCHUTZ.md` |
| m | Gates und Protokoll | erfüllt | Abschnitt A |

## A: Gates

```
backend  ruff check . / ruff format --check .            -> All checks passed / 598 files already formatted (ruff 0.16.10)
         basedpyright (nixpkgs 1.39.8, --pythonpath .venv)  -> 0 errors, 0 warnings, 0 notes
         pytest -m 'not integration and not e2e and not live and not perf'  -> 1909 passed
         PROVENANCE_STRICT=1 pytest -m 'integration and not e2e and not live and not perf'
                                                         -> 696 passed, 3 failed (18:54 min); siehe unten
         test_rbac_matrix_admin + test_snapshot erneut      -> 30 passed
         pytest tests/contract/test_listmonk_port.py -m 'listmonk or not listmonk'
                                                         -> 18 passed (Fake und echter Listmonk v5.1.0)
         pytest -m perf test_public_perf.py              -> 2 passed
         alembic heads                                   -> 0009_subscriptions (head)
         deploy/compose-lint.sh                          -> compose-lint ok
         deploy/smoke.sh http://127.0.0.1:8082           -> smoke ok (25 locations, mit den B3-Seiten)
         deploy/public-smoke.sh http://127.0.0.1:8082    -> public-smoke ok (2026-11-03-stupa-movienight-memento-omu-123544)
b3       python -m scripts.b3_acceptance                 -> all checks passed (120 ok)
m5b      python -m scripts.m5b_acceptance                -> all checks passed (301 ok; Schemathesis 7602 Fälle, 0 Fehler)
frontend npm run lint / npm run typecheck                -> sauber
         npx tsc -p e2e/tsconfig.json --noEmit           -> sauber
         npx jest                                        -> 210 Suites, 1695 passed, 1 skipped, 1 todo
         npm run build                                   -> Initial total 654,33 kB (170,66 kB übertragen)
e2e      E2E_BASE_URL=http://localhost:4200 getstarted.spec.ts   -> 8 passed (2,3 min)
```

Zu den drei Fehlern im Gesamtlauf:

- `test_rbac_matrix_admin[admin]` und `[editor]`: Die neuen Digest- und Statusrouten (Fix E5) antworteten in der
  Matrix 503, weil dort keine Abo-Datenbank konfiguriert ist. Die Matrix bekommt jetzt Datenbank und Fake-Listmonk
  (Fix E13). Danach ist sie grün.
- `test_snapshot.py::test_the_job_reads_through_the_public_engine_by_default`: `too many connections for role
  "events_public"`. Das ist derselbe Befund wie in B1. Die Rolle hat `CONNECTION LIMIT 8` clusterweit im
  Testcontainer, und der Gesamtlauf hält zu der Zeit schon Verbindungen. Allein läuft die Datei grün. Der Punkt steht
  weiter unter "Offen" (Poolgröße).

basedpyright aus der venv startet auf NixOS nicht (dynamisch gelinktes Node). Gelaufen ist dieselbe Version aus
nixpkgs.

## B: `scripts/b3_acceptance.py` gegen den Dev-Stack

Ablauf: Login über Keycloak (`organizer-fsi`, `editor`). Die FSI veröffentlicht eine Party und eine StuPa-Sitzung in
der laufenden Berliner Woche (25.10., 18:00). Danach laufen die Punkte über die öffentliche API ohne Cookie. ALTCHA wird
je POST frisch gelöst. Die Mails kommen aus Mailpit, die Listmonk-Jobs laufen per `enqueue_job` auf dem laufenden
Worker. Mit SQL liest das Skript nur (als Superuser, weil `events_app` die Abo-Tabellen nicht sieht). Eine Ausnahme ist
die Digest-Woche: Sie setzt das Skript vor Punkt f zurück, damit ein zweiter Lauf in derselben Woche wieder
Entwürfe sieht. Die Rate-Limit-Zähler der Abo-Routen in Redis werden zwischen den Zeitmessungen geleert. Letzter Lauf:
`all checks passed`.

**a, "nur Partys, keine Sitzungen".** Anmeldung ohne Mail ergibt 202 ohne `Set-Cookie`, Kategorien `party`,
`campusfest`, `festival`, `get-together`, eine `webcal://`- und eine `https://…/ics/p/<43 Zeichen>.ics`-Adresse. Der
Kalender antwortet `text/calendar` mit 9 Events. Alle 9 gehören zu Party-Kategorien, die neue Party ist enthalten, die
Sitzung nicht und kein anderes Sitzungs-Event. Dasselbe mit Mail: DOI-Mail, POST-Bestätigung, `outbox_run`. Danach
steht in Listmonk genau `events-alle`, `events-campusfest`, `events-festival`, `events-get-together` und
`events-party`, alle `confirmed`, mit Attribut `kategorien`. Eine `events-sitzung` gibt es nicht, und Listmonk schickt
keine eigene Opt-in-Mail.

**b, GET bestätigt nicht.** Nach der Anmeldung ist der Status `pending`. `GET /bestaetigen/<token>` auf der API (8000)
und auf `ng serve` (4200) antwortet 200, ohne den Token im HTML zu wiederholen. Der Status bleibt `pending`, auch nach
`confirm/preview`. Erst der POST bestätigt und löscht den Hash des DOI-Tokens. Ein zweiter POST bekommt dieselbe 404.

**c, gleiche Antwort und Zeit.** Gemessen wurde nur der POST, das ALTCHA ist schon vorher gelöst. Je 10 Messungen für
eine bestätigte Adresse und für frische Adressen, dazu `manage-link` für beide:

```
                 Median     min..max
known            604,7 ms   603,0..605,9
unknown          605,3 ms   603,7..606,7
link-known       605,1 ms   603,2..606,8
link-unknown     605,5 ms   604,0..606,0
```

Status ist immer 202. Der Körper der Anmeldung ist byte-gleich, wenn man den neuen Kalender-Token maskiert. Der
Körper von `manage-link` ist byte-gleich ohne Maske. Keine Antwort kam schneller als 0,6 s. Die bekannte Adresse hatte
ihre drei Mails des Tages bald verbraucht. Die Antwort blieb trotzdem gleich, das stille Auslassen der Mail ist also
nicht sichtbar.

**d, Rotation (B2).** Über den Verwaltungslink aus Mailpit wird `POST me/ics-token` aufgerufen. In der DB steht dann
nur `sha256` des neuen Tokens. Der neue Token antwortet 200. Der alte und ein erfundener Token antworten beide 404 mit
byte-gleichem Körper und gleichem Content-Type.

**e, Listmonk down.** Der Container wird gestoppt (`/health` antwortet nicht mehr). Anmeldung und POST-Bestätigung
klappen trotzdem, die Outbox wächst um 1. `outbox_run` scheitert mit `ConnectError`, der Auftrag bleibt `pending`
(`attempts 1`, Backoff 60 s). Nach dem Neustart läuft der Job weiter. Nach 7 Läufen im Abstand von 10 s ist die Outbox
leer, die Person steht in Listmonk und kein Auftrag ist `dead`.

**f, Digest.** Erst der Abgleich, dann `build_digest_drafts`: Entwürfe für `_all`, `party`, `get-together` und
`kino`. Übersprungen sind `sitzung` und `workshop`, weil diese Listen keinen Subscriber haben. In Listmonk liegen
`events-digest-2026-10-19-*` als `draft`. Es ging keine Digest-Mail heraus, und ein zweiter Lauf legt nichts an. Der
`editor` gibt den Party-Entwurf über `POST /api/admin/digests/{id}/release` frei (Fix E5), die Zählprüfung passt. Die
Kampagne läuft, die Mail kommt in Mailpit an, und die übrigen Entwürfe bleiben ungesendet.

**g, Abmeldung bleibt.** Die Digest-Mail trägt `List-Unsubscribe` (Listmonk-Seite) und
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`. Damit ist die Annahme aus Kontrakt 3.6 belegt. Auf der Seite wird
"Unsubscribe from all future e-mails" abgeschickt (`blocklist=true`), Listmonk steht danach auf `blocklisted`. Erster
Abgleich: unser Datensatz wechselt von `confirmed` auf `unsubscribed`, die Profil-Mail ist aus. Danach laufen
`outbox_run` und ein zweiter Abgleich: es bleibt `unsubscribed`, Listmonk bleibt `blocklisted`.

**h, Löschen.** Über den Verwaltungslink lädt `GET me` ohne Kalender-URL, danach `DELETE me` mit 204. Zurück bleibt
ein Grabstein `erased`: `email_enc`, `email_hmac`, Token-Hashes und `listmonk_subscriber_id` sind `NULL`. Das Profil
samt Kalender-Token ist weg, der Verwaltungstoken gibt 404. Der `delete`-Auftrag ist `done` und ohne Chiffrat, in
Listmonk gibt es keinen Datensatz mehr.

**i, Tokens und Logs.** Der Lauf hat 28 Tokens und 23 Adressen benutzt. Gesucht wurde nach jedem Token, jeder Adresse
und jedem Lokalteil:

- `pg_dump` der fünf Abo-Tabellen: kein Token und keine Klartext-Adresse, dafür die SHA-256 der lebenden
  Kalender-Tokens.
- Journale seit Laufbeginn: `stupa-api` (6 Zeilen), `stupa-worker` (86), `stupa-ng` (0), Postgres (1), Listmonk
  (14, nur Tokens gesucht, Listmonk kennt die Adressen). Kein Treffer.
- nginx mit der Produktionskonfiguration: jeder Token einmal auf `/ics/p/`, `/abo/` und `/bestaetigen/`, dazu ein
  Bestätigungs-POST, zusammen 424 Zeilen. Kein Treffer, die Zeilen lauten `"GET /ics/p/..."`, `"GET /abo/..."` und
  `"GET /bestaetigen/..."`.
- Redis außerhalb der arq-Mail-Jobs (die den Mailtext absichtlich tragen): kein Token, keine Adresse.

Vor Fix E7 schrieb der Worker zu jeder Mail die Empfängeradresse ins Journal.

## C: Playwright `getstarted.spec.ts` (gegen `ng serve` :4200, Mailpit, Listmonk)

```
✓ questionnaire to profile calendar: only parties, no meetings, no cookie
✓ a reload of the result page starts again at step 1
✓ mail path: DOI mail, GET confirms nothing, the button does, manage, new address, delete (1,6 min)
✓ the same result page for a known and an unknown address
✓ an expired or invented link says one sentence and changes nothing
✓ axe in light and dark on the new pages (phone)
✓ axe in light and dark on the new pages (desktop)
✓ network allowlist over the new pages: own origin, no Set-Cookie, no cookie
8 passed (2,3 min)
```

Die Spec lief vorher nie gegen das echte Backend. Drei Fixes waren nötig (E8 bis E10).

## D: Bestehende Abnahmen

- `m5b_acceptance` (alle Punkte a bis h): `all checks passed`. Die Live-Schemathesis deckt jetzt auch die Abo-Routen ab
  (7602 Fälle). Dafür waren Fix E11 und E12 nötig.
- Kanarienvogel (`tests/integration/publicapi/test_canary.py`, `subscriptions/test_subs_canary.py`) und Schemathesis
  in-process liefen im Integrationslauf grün.
- `smoke.sh` und `public-smoke.sh` liefen gegen den nginx-Wegwerf-Container auf 8082. Die Log-Probe von
  `public-smoke.sh` liest dabei über ein Hilfsskript das Journal von nginx-Container und `stupa-api` statt
  `docker compose logs`. Der Compose-Produktionsstack (8081) wurde für B3 nicht gebaut.

## E: Fixes der Integration (eigene Commits)

1. `0a3d105 fix(test)`: Die synchrone Fixture `fake` lief unter `pytest_asyncio.fixture` (basedpyright-Fehler).
2. `7198404 fix(listmonk)`: Wer sich nach einer Abmeldung neu anmeldete und bestätigte, blieb für immer
   abgemeldet. Der Worker ignorierte den Marker `reconfirmed` im Outbox-Payload, und "Listmonk gewinnt" ließ Blocklist
   und Listen-Abmeldung stehen. Der Port hat jetzt `resubscribe()`: `PUT /api/subscribers/{id}` mit `enabled` hebt die
   Blocklist auf, `PUT /api/subscribers/lists` mit `add`/`confirmed` bestätigt die Listen neu. Beides ist gegen v5.1.0
   geprüft, dazu kommen ein Vertragstest (Fake und echt) und ein Integrationstest.
3. `0fcbb16 fix(deploy)`: `dev-up.sh` liest die optionale, gitignorierte Überlagerung `backend/dev.env.local` nach
   `backend/.env`. Das Listmonk-Seed schreibt seinen Token dorthin, wenn es sie gibt.
4. `2061a0e`, `6bac69e fix(subs)`: `/abo` und `/bestaetigen` ohne Token liefern die nackte Hülle (noindex, no-store,
   no-referrer). Vorher endete ein Reload nach dem `replaceState` der SPA in einer 404.
5. `2634188 feat(subs)`: Die Verdrahtung fehlte. Neu sind `GET /api/admin/digests` und
   `POST /api/admin/digests/{id}/release` (`digest.release`, mit Zählprüfung und Breaker) sowie
   `GET /api/admin/subscriptions/status` (`subscriber.stats`: Rückstand, `dead`, `dead`-Löschaufträge, Breaker, letzter
   Abgleich). Der Listmonk-Client wird an einer Stelle gebaut (`client_from_settings`).
6. `084d45b fix(deploy)`: nginx leitet `/start` und `/abos` an die API-Hülle. Vorher landeten sie in der statischen
   SPA ohne Kopfblock. Die Token-Location nimmt auch die nackten Pfade und setzt `Cache-Control: no-store`.
   `compose-lint` verwechselt `/abos` nicht mehr mit einer Token-Seite.
7. `28c5de5 fix(worker)`: arq loggt beim Start jedes Jobs die Argumente. Bei `send_mail` waren das Empfänger, Betreff
   und Textanfang. Jede DOI- und Verwaltungsmail stand so mit Adresse im Worker-Journal, und das gilt schon seit M4 für
   alle Benachrichtigungsmails. Ein Filter auf `arq.worker` ersetzt die Argumente durch "…".
8. `b548e8b fix(e2e)`: `email-validator` weist die Sonder-TLD `.test` ab, die Spec meldet jetzt `@example.org` an.
9. `3b0d972 fix(e2e)`: Der Listmonk-Helfer nutzte `query=`, das `subscribers:sql_query` braucht und deshalb 403
   bekam. Er sucht jetzt mit `search=` und exaktem Vergleich.
10. `37f4779 fix(e2e)`: "Link anfordern" traf auch den Knopf "Verwaltungslink anfordern" hinter dem Dialog. Die Spec
    sucht jetzt im Dialog.
11. `87c2170 fix(subs)`: `PUT /api/public/subscriptions/me` dokumentiert seine 429.
12. `9d58853 fix(scripts)`: Die Live-Schemathesis überspringt negative Fälle, deren Header-Wert kein HTTP-Client senden
    darf (8 Fälle, gezählt). Fehlergruppen (`BaseExceptionGroup`) werden gesammelt statt den Lauf abzubrechen.
13. `b86d6c7 test(admin)`: Die RBAC-Matrix bekommt für die neuen Routen Datenbank und Fake-Listmonk.
14. `244114a fix(listmonk)`: arq gibt jedem Job eine Kopie des Kontexts. Die im `ctx` zwischengespeicherte Subs-Engine
    entstand daher bei jedem `outbox_run` neu. Nach wenigen Minuten hielt der Worker das ganze `CONNECTION LIMIT 6` von
    `events_subs`, und die Jobs scheiterten mit "too many connections". Engine und Client sind jetzt einmal je Prozess
    vorhanden.
15. `55883ed`, `3e5831e`: `smoke.sh` prüft die B3-Seiten. `public-smoke.sh` akzeptiert die anonyme 401 von
    `/api/auth/me`, die seit `543433d` jeden Lauf scheitern ließ, und prüft `/start`, `/abos` und den Fragebogen auf
    Cookies.
16. `99e4589 test(b3)`: `scripts/b3_acceptance.py` mit `b3_api`, `b3_flow`, `b3_listmonk`, `b3_secrets` und `b3_ops`.

Kontraktannahmen, die gegen Listmonk v5.1.0 nicht stimmten, hat der Builder schon korrigiert (`listmonk_client.py`):
Es gibt kein `PATCH` auf Subscriber, die Suche läuft über `search` statt `query`, der Health-Pfad heißt `/health`, und
die Zählung läuft über `subscription_status=confirmed`.

## Offen

- **Gate B3:** Die schriftliche Rückmeldung der Datenschutzbeauftragten zu `docs/B3-DATENSCHUTZ.md` fehlt. Bis dahin
  gilt B3 als "technisch fertig, Gate offen", und der Go-live (B5) bleibt gesperrt.
- **`backend/.env` zusammenführen:** Luis entscheidet, ob die Schlüssel aus `backend/dev.env.local` nach
  `backend/.env` wandern oder die Überlagerung bleibt. Die Datei ist gitignoriert und enthält frische Dev-Schlüssel und
  den Listmonk-Token.
- **Freigabe-Knopf in der App (I25):** API-Route und Statuszähler gibt es, eine Oberfläche nicht. Heute erfolgt die
  Freigabe über die Route oder direkt im Listmonk. Der Abgleich erkennt eine Freigabe im Listmonk
  (`mark_released_in_listmonk`).
- **Bounces** setzt der Abgleich nie (`bounced`). Die Subscriber-API unterscheidet einen Bounce nicht von einer
  Hand-Blocklist (Builder-Befund).
- **Weiche B3-3:** Der API-Nutzer hat `lists:manage_all`, weil Listmonk Listen-Rollen nur mit konkreten IDs kennt. Die
  Handarbeit für die Produktion steht in `docs/secrets.md`.
- **Weichen B3-1 und B3-2:** Die Zuordnung Interessen → Kategorien (Kontrakt 2.1) ist ein Vorschlag. Reine
  Kalender-Profile haben keine Verwaltung.
- **Schreib-Limit der öffentlichen POSTs:** `DefaultWriteRateLimitMiddleware` zählt auch die Abo-POSTs (100 je IP und
  Stunde). Hinter einem Campus-NAT kann das vor dem eigenen Limit von 10/h greifen. Luis: Abo-Pfade ausnehmen?
- **Poolgröße `events_public`** wie in B1 (Integrationsfehler `test_snapshot`). Neu ist dieselbe Frage für
  `events_subs`: `CONNECTION LIMIT 6` für API (3+1) und Worker (2) zusammen lässt keine Reserve, etwa für eine zweite
  API-Instanz.
- **`.test`-Adressen** weist die API ab. Für Tests `example.org` nehmen, Mailpit fängt alles ab.
- **Tageslimit je Adresse in Testläufen:** 3 Mails je Adresse und Tag zählen hart in der DB. Wiederholte Läufe brauchen
  frische Adressen, das Skript erzeugt sie.
- **Testdaten:** In der Dev-DB und im Listmonk liegen die Subscriber, Profile, Digest-Läufe und Kampagnen der
  Abnahmeläufe, dazu je Lauf eine Party und eine Sitzung der FSI. Im Listmonk liegen außerdem Reste der
  Builder-Tests ("Test campaign", "probe-unsub").
- **Ergänzungen der Builder ohne Kontraktgrundlage:** die Mail "Du bist schon angemeldet" (`already`), der Konflikt
  `questionnaire_outdated` (409) und `consent_categories` mit aufgelösten Kategorie-Slugs (Builder-Hinweise). Kontrakt
  nachführen.
- **Ports und Abweichungen im Dev-Stack:** Mailpit-SMTP liegt auf 1026, weil Proton Bridge 1025 belegt. Die Mails der
  Abo-Routen enthalten den Link mit Token, deshalb liegt er im arq-Job in Redis, bis der Job-Status abläuft
  (Kontrakt-konform).
