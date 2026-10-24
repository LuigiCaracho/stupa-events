# Abnahme B1/B2: öffentliche Seite

Stand 2026-10-24, Branch `feat/b1-public` (von `feat/m5b-vereinfachung` @ `e43a482`), nichts gepusht. Grundlage:
`docs/B1-KONTRAKT.md` Abschnitt 7. Alles lief lokal: Dev-Dienste aus `deploy/docker-compose.dev.yml`, API und Worker als
User-Units (`stupa-api`, `stupa-worker`), `ng serve` auf 4200, Keycloak 8090. Der Produktions-Build hinter nginx lief als
Compose-Stack (`web` auf 8081) und ist danach wieder heruntergefahren. Kein Live-System berührt.

## Ergebnis

B1 ist **erfüllt**, mit den offenen Punkten unten. B2 besteht in diesem Schnitt nur aus der Abos-Seite P07 (ICS je
Kategorie und `all`). Profil-ICS und Token kommen mit B3 (Kontrakt 8.1).

| # | Prüfpunkt | Ergebnis | Beleg |
|---|---|---|---|
| a | Link-Vorschau Matrix, WhatsApp, Signal: Titel und Poster | per curl erfüllt; Darstellung in den Apps nicht geprüft | Abschnitt B |
| b | 20 Mustersuchen | erfüllt | `test_search_corpus.py`, Perf-Lauf auf 5000 Events, HTTP-Probe gegen 8081 (Abschnitt C) |
| c | 5000 Events, p95 < 300 ms | erfüllt (Suche 77,1 ms, Liste 27,4 ms) | Abschnitt C |
| d | kein `Set-Cookie` | erfüllt | `public-smoke.sh`, Playwright Allowlist, Abschnitt B |
| e | Netzwerk-Allowlist-E2E | erfüllt gegen 8081 und 4200 | Abschnitt D |
| f | axe ohne `critical`/`serious`, hell und dunkel, 390×844 und 1280 | erfüllt gegen den Produktions-Build hinter nginx und gegen `ng serve` | Abschnitt D |
| g | Sitemap, robots, Log ohne Query | erfüllt nach Fix E1 | Abschnitt B |
| h | Seiten P01 bis P05, P07, P10 (nur heute), P13, P14 | erfüllt | `public.spec.ts` 1 bis 5 |
| i | B2 Token-Hash, Rotation, dieselbe 404 | gehört nicht zu dieser Abnahme | Kontrakt 8.1, B3 |
| j | Gates | erfüllt | Abschnitt A |

## A: Gates

```
backend  ruff check . / ruff format --check .          -> All checks passed / 511 files already formatted (ruff 0.16.10)
         basedpyright                                   -> 0 errors, 0 warnings, 0 notes
         pytest -m 'not integration and not e2e and not live'  -> 1710 passed
         PROVENANCE_STRICT=1 pytest -m integration      -> 581 passed, 1 failed (16:17 min); siehe unten
         test_snapshot.py erneut, Compose-Stack aus     -> 10 passed
         test_search_corpus + test_canary + test_schemathesis  -> 32 passed
         pytest -m perf test_public_perf.py             -> 2 passed
         alembic heads                                  -> 0008_public_site (head)
         deploy/compose-lint.sh                         -> compose-lint ok
         deploy/smoke.sh http://127.0.0.1:8081          -> smoke ok (18 locations)
         deploy/public-smoke.sh http://127.0.0.1:8081   -> public-smoke ok (2026-11-03-stupa-movienight-memento-omu-123544)
m5b      python -m scripts.m5b_acceptance               -> all checks passed (299 ok; Schemathesis 4606 Fälle, 0 Fehler)
frontend npm run lint / npm run typecheck               -> sauber
         npx jest                                       -> 202 Suites, 1624 passed, 1 skipped, 1 todo
         npm run build                                  -> Initial total 641,36 kB (168,15 kB übertragen)
e2e      E2E_BASE_URL=http://127.0.0.1:8081 public.spec.ts      -> 9 passed, 1 failed (Login, siehe D)
         E2E_BASE_URL=http://localhost:4200 public.spec.ts      -> 10 passed (1,6 min)
         E2E_BASE_URL=http://localhost:4200 m1..m5, m5b         -> 34 passed (4,0 min)
```

Der eine Integrationsfehler (`test_snapshot.py::test_the_job_reads_through_the_public_engine_by_default`, `too many
connections for role "events_public"`) kam vom Aufbau der Abnahme. Die Rolle hat `CONNECTION LIMIT 8` clusterweit, und
während des Laufs hielten Dev-API, Dev-Worker und die Compose-API zusammen schon 8 Verbindungen. Ohne Compose-Stack ist
die Datei grün. Der Befund zur Poolgröße steht unter "Offen".

## B: Produktions-Build hinter nginx (8081)

Aufbau: `docker compose -f deploy/docker-compose.yml --env-file deploy/.env.dev up -d --build web` mit einer
Wegwerf-Überlagerung (`/tmp/b1-int/compose.devdata.yml`, nicht im Repo). Sie hängt `api` und `migrate` zusätzlich ins
Netz `stupa-events-dev_default` und richtet Postgres, Redis und MinIO auf die Dev-Container. So liefert `web` die
vorhandenen Dev-Daten samt Fixtures mit Poster. Ein leerer Compose-Bestand hätte erst Events über einen Login gebraucht,
und der Login scheitert auf 8081 (Abschnitt D). Gebaut wurden beide Images, `api` mit der Stufe `spa`.

Link-Vorschau, je drei User-Agents (`WhatsApp/2.24.1`, `Synapse (bot; +https://github.com/element-hq/synapse)`,
`Signal-Desktop/7.0`), `public-smoke.sh` zusätzlich mit `facebookexternalhit/1.1`:

```
/                     200  og:title og:image og:url  JSON-LD 0  CSP 1  Set-Cookie 0  public, max-age=60, stale-while-revalidate=30
/e/<slug>             200  og:title og:image og:url  JSON-LD 1  CSP 1  Set-Cookie 0  (dto.)
/k/kino               200  og:title og:image og:url  JSON-LD 0  CSP 1  Set-Cookie 0  (dto.)
Körper je Pfad über alle Agents byte-gleich (1 Prüfsumme je Pfad)
og:image  http://localhost:8081/api/public/media/a6a481f59d91121a-og_1200x630.webp  -> 200 image/webp
JSON-LD   Event, name, startDate 2026-10-31T19:00:00+01:00, eventStatus EventScheduled, image vorhanden
```

JSON-LD gibt es nur auf `/e/…`, wie Kontrakt 2.8 es festlegt. `/` und `/k/…` tragen Open Graph ohne JSON-LD.

Weitere Befunde auf 8081:

- `ETag` und `If-None-Match` geben 304; die Hülle und `/index.html` nennen dieselben `main-*.js`/`styles-*.css`.
- Kein `Set-Cookie` auf `/`, `/suche`, `/kalender`, `/rueckblick`, `/sitemap.xml`, `/robots.txt`, `/api/public/events`,
  `/api/public/today`, `/ics/e/<slug>.ics`, `/api/auth/me`.
- Access-Log: 94 GET-Zeilen, keine mit `?`. Nach Fix E1 erreichen `GEHEIM…`-Suchen weder den `web`- noch den
  `api`-Log, auch nicht als 429 (16 schnelle Abrufe von `/suche?q=GEHEIMRL…`: 11 × 200, 5 × 429, 0 Logtreffer).
  Die zwei `GEHEIM`-Zeilen im gesicherten Log stammen aus dem Lauf vor dem Fix (19:09:35 und 19:09:39 UTC).
- Proxy-Cache: der zweite `/api/public/today` kommt mit `X-Cache-Status: HIT`.
- `robots.txt` im Wortlaut von Kontrakt 2.8; `sitemap.xml` wohlgeformt, 474 URLs.
- Speicher von `web` unter Last (3000 Abrufe, 30 parallel, Suche und Detail): 19,5 bis 22,7 MiB von 64 MiB.
  Codes: 45 × 200, 2946 × 429 (nginx `limit_req`, eine IP), 9 × 500. Die 500 sind `too many connections for role
  "events_public"` in der Compose-API, siehe "Offen".

ICS (Parser `icalendar` 7.3.0):

```
/ics/k/kino.ics     text/calendar, inline       VERSION 2.0, 309 VEVENT, alle mit UID/DTSTAMP/DTSTART/SUMMARY, VTIMEZONE Europe/Berlin (RRULE)
/ics/e/<slug>.ics   text/calendar, attachment   1 VEVENT, SEQUENCE 1, STATUS CONFIRMED
/ics/all.ics        text/calendar               328 VEVENT, alle Pflichtfelder
```

Die `webcal://`- und `https://`-Adresse auf `/abos#k=<slug>` prüft `public.spec.ts` 4 (Kopieren, `text/calendar`).

## C: Last und Suche

`python -m scripts.b1_load`: Wegwerf-Postgres, 5000 synthetische Events, je 200 Anfragen über die ASGI-App ohne
Antwort-Cache, eine API-Instanz, parallel lief die Integrationssuite nicht mehr.

```
route             n   median      p95      max
list            200     15.7     27.4    258.7
list-search     200     60.2     77.1    223.2
list-category   200     13.3     20.0     28.3
list-range      200     16.8     27.6     39.9
detail          200      2.1      4.4      6.2
today           200      6.2      8.8     11.7
calendar        200      9.4     15.1     16.1
```

Der Plan der Textsuche zeigt `Seq Scan` auf `event`, weder `ix_event_search_tsv` noch den Trigram-Index. Die Annahme
aus Kontrakt 2.1 Punkt 4 (der Planer schiebt die Bedingung durch die View) ist damit **nicht belegt**. Bei 5000 Events
bleibt die Suche weit unter der Marke.

Die 20 Mustersuchen bestehen im Integrationstest gegen den festen Bestand und im Perf-Lauf auf 5000 Events
(`test_the_samples_still_hit_on_the_big_stock`). Gegen 8081 mit Dev-Daten antworteten alle 19 gültigen Suchen 200,
die Eingabe mit 114 Zeichen 422 `query_too_long`, die Sonderzeichen ohne Fehler. Auf den Dev-Daten fand `Kino` nichts,
obwohl die Kategorie Kino 270 Events hat (siehe "Offen").

## D: Playwright

`public.spec.ts` gegen 8081 (Produktions-Build, nginx, CSP): Heute → Detail → ICS, Suche mit Facette, Kalender,
Kategorie-Abo, Phone 390×844 (kein waagrechtes Scrollen, Bottom-Bar, 44-px-Ziele, Filter-Sheet mit Fokusfalle), axe
hell und dunkel auf allen Routen für Desktop und Phone, Netzwerk-Allowlist (nur eigene Origin, kein `Set-Cookie`, am
Ende keine Cookies) und die Fehlerzustände: grün. Der Login-Test scheiterte auf 8081: `deploy/.env.dev` setzt
`OIDC_ISSUER=http://host.docker.internal:8090/…`, und den Namen kennt der Browser auf dem Host nicht. Gegen 4200 läuft
die ganze Datei grün, der Login-Test eingeschlossen. axe protokolliert keine `moderate`-Befunde; der Test filtert nur auf
`serious` und `critical`.

## E: Fixes der Integration (eigene Commits)

1. `fix(deploy)`: nginx schrieb bei jeder `limit_req`-Ablehnung die volle Anfragezeile ins Error-Log, also
   `/suche?q=…`. Ablehnungen loggen jetzt auf `info` (unter `notice` des Images) und antworten 429 statt 503. Die SPA
   zeigt für 429 "Zu viele Anfragen. Bitte warte einen Moment.". `public-smoke.sh` wartet vor der Log-Probe drei
   Sekunden, sonst lief sie selbst in den `ev_page`-Burst.
2. `fix(frontend)`: Karten und Kalendereinträge vertragen `startsOn`/`endsOn = null` (die API füllt sie nur bei
   ganztägigen Events). Die Suche zeigte vorher "1 Treffer" ohne Zeilen. `PROVENANCE.json` streicht die neu
   geschriebenen `public-header` und `site-footer` und den entfernten `home-redirect.guard`.

## Offen

- **Poolgröße der Public-Rolle:** `events_public` hat `CONNECTION LIMIT 8`, die Public-Engine `pool_size=4,
  max_overflow=2` je Prozess, und API und Worker (`worker/public_cache.py`) nutzen sie beide. Zusammen sind bis zu 12
  Verbindungen möglich. Bei einem Ansturm auf Cache-Fehlschläge antwortet die API dann 500 statt 503. Hier trat das nur
  mit zwei API-Instanzen auf; in Betrieb reicht ein beschäftigter Worker. Luis: kleinerer Pool im Worker oder ein
  höheres Limit?
- **Suche findet keine Kategorie-, Orts- und Organisationsnamen.** `search_tsv` umfasst nur Titel, Summary und
  Beschreibung (Kontrakt 2.2.1, wie intern). Die Pflichtmuster "Party", "Rappen" und "FSI" bestehen, weil die Wörter im
  Bestand im Titel stehen. Mit Dev-Daten findet "Kino" keines der 270 Kino-Events. Luis: Kategorie, Ort und
  Organisation in die Suche aufnehmen (Migration der View oder Zusatzbedingung)?
- **Index-Pushdown** der Suche nicht belegt (Seq Scan, Abschnitt C); vor größerem Bestand prüfen, Teilindex aus
  Kontrakt 2.1 Punkt 4 als erster Schritt.
- **WebP als `og:image`** in WhatsApp und Signal und die Vorschau in Element nicht in den Apps geprüft (Kontrakt 6.3
  Punkt 6); braucht einen öffentlich erreichbaren Host.
- Login auf dem Compose-Stack: der Issuer `host.docker.internal` ist vom Browser nicht erreichbar. Der Test
  "Angemeldet" läuft deshalb nur gegen 4200. `docker-compose.keycloak.yml` verlangt dafür einen Eintrag in der
  Hosts-Datei des Rechners; den habe ich nicht angelegt.
- Rate-Limit-Startwerte 120 und 30 je Minute und nginx `ev_page` 5 r/s mit Burst 10 sind ungemessen. Hinter Campus-NAT
  kann der Burst knapp werden.
- `proxy-cache.conf` setzt `X-Cache-Status` auch in Produktion, Kontrakt wollte es nur in der Smoke-Variante.
- Kontrakt 2.8 sagt "ICS ohne VTIMEZONE", der M5-Schreiber liefert VTIMEZONE (mit RRULE) und `X-WR-CALNAME` mit
  Präfix "STUPA Events: ". Goldens unverändert, Kontrakt nachführen.
- `startsOn`/`endsOn` sind in der API nur bei ganztägigen Events gesetzt, der Kontrakt führt sie ohne Nullbarkeit.
  Kontrakt klarstellen.
- OpenAPI-Warnungen "Duplicate Operation ID" für die GET/HEAD-Routen der Hülle (`sitemap_xml`, `robots_txt`) und der
  ICS (bestanden schon vor B1).
- `backend/.env` setzt `PUBLIC_BASE_URL=http://localhost:4200`; die Backend-Tests laufen nur ohne diese Variable
  (`env -u PUBLIC_BASE_URL`).
- Etwa 30 Abnahme-Dossiers aus `m5b_acceptance` und Playwright liegen zusätzlich in der Dev-DB.
