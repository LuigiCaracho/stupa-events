# Abnahme C1 bis C4 (Karten) und B4 (PWA, EN)

Stand 2026-10-25, Branch `feat/c-karten` (von `feat/b3-abos`), nichts gepusht. Grundlage: `docs/C-KONTRAKT.md`
Abschnitt 6.5 (Wortlaut PLAN 16.2 B4 und 16.3 C1 bis C4). Alles lief lokal: Dev-Dienste aus
`deploy/docker-compose.dev.yml` (neu gestartet: `tiles` auf 8083), API und Worker als User-Units (`stupa-api`,
`stupa-worker`, gestartet nach dem letzten Backend-Commit), `stupa-ng` neu gestartet (Asset-Kopie `/map/` aus
`angular.json`), Keycloak 8090. Kein Live-System berührt. Externe Zugriffe: nur `scripts/build-tiles.sh fetch`
(Protomaps-Build 20261024). Overpass lief einmal beim Backend-Builder (`docs/C-CAMPUS-OSM.md`), Nominatim gar nicht.

**Full-Stack-web.** Das Image `deploy/web/Dockerfile` wurde gebaut (Produktions-Build im Image, `nginx.conf`,
Snippets und CSP aus dem Image). Es lief mit `--network host` auf 8081 vor der Host-API. Die `listen`-Zeile wurde auf
8081 umgeschrieben, sonst blieb die Konfiguration unverändert. Die Tiles kamen aus dem Volume `stupa-c-int_tiles_data`.
Das Volume hat `scripts/build-tiles.sh install` befüllt und danach selbst geprüft. Container, Volume und Image sind
danach entfernt.

**Daten.** Davos, Ischgl, Europapark und Straßburg haben auf der Dev-DB keine Koordinate. Sie bekommen erst eine mit
Luis' Lauf `pin_venues --live` (W-C6). Deshalb pinnt `python -m scripts.c_acceptance setup` diese vier von Hand über
den echten Admin-Weg (I23, `PATCH /api/admin/venues/{id}`, Quelle `pin`, Präzision `building`). Danach veröffentlicht
die FSI über die API je ein Event dort und heute je eines in Kinosaal 9-133, Maker Space 9-229 und FSI 9-U09. Dazu kommen
ein abgesagtes Event in 9-133 und eines an einem privaten Ort mit Koordinate in Gebäude 9. `teardown` hat die Pins
zurückgesetzt und den privaten Ort deaktiviert. Die Events bleiben in den Dev-Daten, ihre Orte sind wieder `hidden`.

## Ergebnis

| Kriterium | Ergebnis | Beleg |
|---|---|---|
| C1 Karte ohne Request an Dritte | erfüllt (echt) | `real-map.spec` 1: nur die eigene Origin über `/karte` und `/campus`, alle `/tiles/`-Antworten 206, keine CSP-Verletzung, kein `Set-Cookie`; `map.spec` T1 |
| C1 Range-Requests hinter nginx | erfüllt (echt) | `deploy/tiles-smoke.sh http://127.0.0.1:8081` → `tiles-smoke ok`; `bytes=0-16383` → 206, `Content-Range bytes 0-16383/15048644`, `Accept-Ranges`, starkes ETag, 7 Tage Cache; Bereich hinter dem Ende → 416 |
| C2 Orte mit Koordinate oder `hidden`, privat nie extern, kein Autocomplete | erfüllt auf der Dev-DB; Pin-Lauf offen | Abschnitt B |
| C3 Davos, Ischgl, Europapark, Straßburg; Liste gleich; keine Koordinate im Request | erfüllt mit Hand-Pins; die Nominatim-Pins fehlen noch | Abschnitt C |
| C4 Gebäude 9 zählt korrekt, keine OSM-Abhängigkeit zur Laufzeit | erfüllt (echt) | Abschnitt C |
| B4 Heute offline, EN-Parität, Update-Prompt | erfüllt | Abschnitt D |
| Gates | erfüllt bis auf zwei Punkte | Abschnitt A: Bundle +8,57 kB über dem B3-Stand, B3-Punkt f wegen Listmonk-Drift in den Dev-Daten |

## A: Gates

```
backend  ruff check . / ruff format --check . (nixpkgs 0.16.10)  -> All checks passed / 629 files already formatted
         basedpyright (nixpkgs 1.39.8, --pythonpath .venv)       -> 0 errors, 0 warnings, 0 notes
         pytest -m 'not integration and not e2e and not live and not perf'  -> 1955 passed (nach Fix 2)
         PROVENANCE_STRICT=1 pytest -m 'integration and not e2e and not live and not perf'
                                                                  -> 742 passed, 2 failed (23:37 min), siehe unten
         test_migration_0005 nach Fix 7                           -> 2 passed
         tests/integration/maps + publicapi/test_canary.py        -> 18 passed
         alembic heads / current (Dev-DB)                         -> 0013_maps (head) / 0013_maps
         deploy/compose-lint.sh                                   -> compose-lint ok
         deploy/smoke.sh http://127.0.0.1:8081                    -> smoke ok (30 locations)
         deploy/public-smoke.sh http://127.0.0.1:8081             -> public-smoke ok (im zweiten Anlauf; der erste
                                                                     direkt nach smoke.sh lief in die 429 von limit_req)
         deploy/tiles-smoke.sh http://127.0.0.1:8081              -> tiles-smoke ok
tiles    scripts/build-tiles.sh fetch / verify / install          -> world 15 048 644 B, reutlingen 17 469 543 B, SHA-256
                                                                     wie tiles.lock; im Volume erneut geprüft
m5b      python -m scripts.m5b_acceptance                         -> all checks passed (301 ok; Schemathesis 9998 Fälle
                                                                     über alle /api/public/- und /ics/-Routen inkl. Karte
                                                                     und Campus, 0 Fehler)
b3       python -m scripts.b3_acceptance                          -> a bis e grün (81 ok), f FAIL count_mismatch, siehe unten
c        python -m scripts.c_acceptance setup / check / teardown  -> alle Punkte ok
frontend npm run lint / typecheck / tsc -p e2e/tsconfig.json      -> sauber
         npx jest                                                 -> 223 Suites, 1804 passed, 1 skipped
         npm run build                                            -> Initial 662,90 kB (173,87 kB übertragen); B3 654,33 kB
         npm run check:map                                        -> map isolation ok
```

Zu den Fehlern:

- `test_migration_0005::test_a_fresh_database_has_the_same_objects` erwartete noch Head `0012_purge_rearmed`.
  Fix 7, danach grün.
- `test_listmonk_live::test_sign_up_digest_release_unsubscribe_and_erase` und B3-Punkt f liegen beide am Dev-Listmonk.
  Der Livetest bekommt beim Kampagnenstart HTTP 400. Bei f verweigert der Release `count_mismatch`. Die eigene DB
  hat 11 bestätigte Party-Abos mit Mail, die Liste `events-party` in Listmonk hat 4 bestätigte und 4 blocklistete.
  7 der 11 stammen aus abgebrochenen B3-Läufen vom 2026-10-24. Der Reconcile reiht sie jedes Mal wieder ein
  (`requeued=18` bis `20`), aber der Idempotenzschlüssel `upsert:<id>:reconcile-<Tag>` lässt nur einen Job pro Tag
  durch. Der Code unter `subscriptions/` ist seit `feat/b3-abos` unverändert (C fügt im Worker nur `gc_geocode_cache`
  hinzu). Das ist Drift in den Dev-Daten, keine Regression durch C. Der Guard greift wie vorgesehen. Siehe Offen.
- `b3_acceptance` direkt nach `m5b_acceptance` scheitert an Punkt a mit 429: Schemathesis leert den Bucket
  `rl:public:ip:127.0.0.1`. Mit Abstand läuft a.

## B: Orte (C2)

- Dev-DB nach `teardown`: 44 aktive öffentliche Orte, davon 8 `building` mit Koordinate (Campus, aus den Polygonen)
  und 36 `hidden` ohne Koordinate. Keiner ist `exact` oder `building` ohne Koordinate. Dazu kommt ein inaktiver
  privater Testort.
- `python -m scripts.pin_venues` (Trockenlauf, ohne Netz): 8 schon gepinnt, 6 per Ortsname und 5 per Adresse offen
  (nur mit `--apply --live`), 25 bleiben verborgen. Das stimmt mit `docs/VENUES-PINNED.md` überein (Kontrakt-Name
  `C-PINS.md`).
- Privater Ort mit Koordinate in Gebäude 9: weder in `map/events` noch in `campus/buildings` oder `campus/events`. Sein
  Name und Titel fehlen in allen drei Antworten (`c_acceptance check`). Unit- und Integrationstests des Backends prüfen
  422 `venue_private` vor jedem Netzzugriff.
- `grep -rniE "nominatim|openstreetmap\.org" frontend/src` (ohne Specs) findet nur den Wert `nominatim` von
  `geocodeSource` und den Label-Schlüssel, keine URL. `grep -rni overpass backend/app` ist leer.

## C: Weltkarte und Campus auf echten Daten (C3, C4)

`c_acceptance check` ohne Cookie: `map/events` enthält die Features Davos `[9.836, 46.803]`, Ischgl, Europapark und
Straßburg (gerundet auf drei Dezimalen, Präzision `building`). `campus/buildings` meldet für Gebäude 9 `count 3`
(abgesagt und privat zählen nicht). `campus/events?building=9` liefert die drei Titel und das abgesagte Event mit
`status: cancelled`.

`E2E_REAL_MAP=1 E2E_BASE_URL=http://127.0.0.1:8081 npx playwright test --project=map` gegen das Full-Stack-web mit den
echten Tiles: **17 von 17 grün**:

| Spec | Ergebnis | Inhalt |
|---|---|---|
| `real-map.spec.ts` (neu, Fix 5) | 5 von 5 | Allowlist mit 206 (C1); Weltkarte: `data-cluster-count > 0`, Trefferliste hat genau `data-feature-count` Zeilen, Davos, Ischgl, Europapark und Straßburg in der Liste (C3); "In meiner Nähe" mit Position Campus: die Campus-Events stehen oben mit Entfernung, kein Request mit `48.48`, `9.18`, `lat=`, `lon=`, `bbox`, `latitude` oder `longitude`, und nach dem Klick überhaupt kein `/api/`-Request (E30); Gebäude 9 in der Tabelle 3, "Anzeigen" ergibt "Gebäude 9: 3 Events" mit den drei Titeln (C4); axe hell und dunkel bei 390 × 844 auf `/karte` und `/campus` |
| `map.spec.ts` (Route-Mocks) | 9 von 9 | T1, T3 (Klick auf Cluster zoomt, Cluster an einem Ort filtert die Liste), T4, T5 (mit und ohne Erlaubnis), T6 (Position nach SPA-Navigation unter aktivem Service-Worker, jetzt mit der unveränderten `security-headers.conf`), T8 axe 1280 und 390, T9 Handy |
| `venue-pin.spec.ts` | 3 von 3 | T7 Pin per Klick, "Adresse suchen" als `nominatim`, privater Ort: Knopf aus, kein Request |

Sichtprüfung der Screenshots (`test-results/real-map-world.png`, `-campus.png`, nicht eingecheckt): Die Weltkarte
zeigt Cluster mit 2 (Straßburg und Europapark), 4 (Campus Reutlingen) und 2 (Davos und Ischgl). Die Campuskarte zeigt
die Umrisse aus OSM, Gebäude 9 ist eingefärbt mit "9: 3", und die Tabelle passt dazu. Zwei Befunde der Sichtprüfung
sind behoben: Fix 3 und 4.

## D: B4

| Spec (Projekt `chromium`) | Gegen | Ergebnis |
|---|---|---|
| `offline.spec.ts` | Full-Stack-web 8081 | grün: Heute offline mit "Offline, Stand HH:MM", zuletzt geöffnetes Event offline lesbar, nie geöffnetes zeigt den Offline-Zustand |
| `pwa-update.spec.ts` | `scripts/pwa-update-stack.sh` 8084 | grün: Prompt mit genau "Neu laden", die neue Version läuft |
| `en.spec.ts` | 8081 | 2 von 2 grün |
| `translations.spec` (Jest, "English parity") | | grün, Teil der 1804 Tests |
| `public.spec.ts` | 8081 | 11 von 13: der Login-Test scheitert wie in B1-ABNAHME D (Keycloak-Rücksprung zeigt auf 4200), der letzte Test der seriellen Datei läuft danach nicht |

Der iOS-Installationshinweis ist per Jest abgedeckt, ein echtes iOS-Gerät stand nicht zur Verfügung.

## Fixes der Integration

1. `161602e fix(deploy)`: `Permissions-Policy` global `geolocation=(self)` (Kontrakt 2.6). Vorher war "In meiner Nähe"
   im echten Stack tot. `e2e-web.sh` patcht die Datei nicht mehr per `sed`.
2. `2271777 fix(frontend)`: Die Provenienzzeile von `ngsw-navigation.spec.ts` fehlte (`test_provenance`, 2 Fehler).
3. `d67cb9e fix(frontend)`: Der Sprunglink "Zur Liste springen" der Karte war dauerhaft sichtbar und verdeckte den
   Zeitfilter. Der `translateY`-Trick schob ihn nur über die Karte. Jetzt bleibt er bis zum Fokus verborgen.
4. `351b5f7 fix(frontend)`: Die Trefferliste zählte "8 Orte" für 8 Events an 7 Orten. Jetzt heißt es "{n} Events",
   ebenso der Kappungshinweis.
5. `e9e9fe7 test(e2e)`: `real-map.spec.ts` für echte Daten, läuft nur mit `E2E_REAL_MAP=1`.
6. `bb58108 test(maps)`: `scripts/c_acceptance.py` (setup, check, teardown).
7. `805be28 test(dossier)`: Der Head-Test von 0005 erwartet `0013_maps`.
8. `c318321 build(deploy)`: `deploy/tiles` (32 MB) ist nicht mehr im Build-Kontext des web-Images.

## Offen

- **Pin-Lauf (W-C6):** Luis führt `python -m scripts.pin_venues --apply --live --contact <Adresse>` gegen die Ziel-DB
  aus (11 Anfragen). Erst danach erscheinen Davos, Ischgl, Europapark und Straßburg ohne Hand-Pins. C3 ist hier nur
  mit Hand-Pins belegt. `NOMINATIM_ENABLED` und `NOMINATIM_CONTACT` sind in keiner Umgebung gesetzt, deshalb antwortet
  der Knopf "Adresse suchen" mit 503 `geocode_disabled`.
- **Bundle-Gate:** Initial 662,90 kB, das sind 8,57 kB über dem B3-Stand von 654,33 kB. Ursache sind die DE-Kataloge
  im Initial-Bundle (alle internen Kataloge, rund 90 kB Quelltext). Den Gate schließen würde nur ein Lazy-Load der
  internen Kataloge (dossier, archive, lifecycle, admin), das ist eine Architekturentscheidung für Luis. `mapDe` allein
  bringt etwa 3 kB.
- **B3-Punkt f und `test_listmonk_live`:** Drift zwischen Dev-DB und Dev-Listmonk (Abschnitt A). Vorschlag: die
  Testabonnent:innen vom 2026-10-24 über den Löschweg entfernen, oder einen frischen Listmonk-Bestand anlegen, und
  dann f erneut laufen lassen. Unklar ist, ob der Reconcile mit Tagesschlüssel eine Lücke im Code ist: Er reiht ein
  fehlendes Abo am selben Tag nur einmal ein.
- **Campusliste:** "Gebäude 9: 3 Events" steht über vier Zeilen, das abgesagte Event ist als "Abgesagt" markiert.
  Das ist kontraktgemäß (Zähler ohne Abgesagte, Liste wie `/events`), wirkt aber widersprüchlich. Zu entscheiden:
  Abgesagte in der Gebäudeliste ausblenden oder in der Überschrift nennen.
- **Attribution:** Auf `/campus` steht "© OpenStreetMap-Mitwirkende (ODbL) | © OpenStreetMap" doppelt (Style und
  `customAttribution`). ODbL-Share-Alike der Polygone ist ungeprüft (W-C7).
- **Gebäude 17 und 11** fehlen auf der Campuskarte (W-C4, `docs/C-CAMPUS-OSM.md`).
- **`backup.sh`** enthält `tiles_data` nicht (W-C3). Der gepinnte Protomaps-Build verfällt um den 2026-10-31,
  danach braucht es `build-tiles.sh bump`. `install` nutzt `alpine:3` ohne gepinnte Version.
- **CI:** Für `npm run check:map` und die Karten- und PWA-Specs gibt es keinen CI-Job. `real-map.spec` braucht Dev-Daten
  und läuft nur lokal.
- **Umgebung:** Rund zwölf Testcontainer (postgres und redis, Namen wie `peaceful_hopper`) laufen seit Stunden weiter.
  Sie stammen nicht aus dieser Integration und sind nicht angefasst.
- Bekannte Grenzen aus dem Frontend-Teil bleiben: Die Server-Hülle `/e/<slug>` und die DB-Texte bleiben deutsch.
  `/campus` markiert keinen Navigationseintrag. Für kyrillische und arabische Namen fehlen Glyphen (404 je `.pbf`,
  wird ignoriert). Die Welt-Region-Kante bei Zoom 7 ist sichtbar.

## Abweichungen vom Kontrakt (Frontend, unverändert)

Icon `pin` statt `map`. Style-Pfade `style-light.json` und `style-dark.json`. Die Handy-Trefferliste steht unter der
Karte. Die Campus-Gebäudeliste steht unter der Tabelle. Die Jahresauswahl zeigt die letzten fünf Jahre. Flächenfarben
kommen aus `--color-accent`-Tokens. Die Test-Tiles sind 2,4 MB statt unter 1 MB. Die EN-Kataloge sind TS-Dateien mit
`satisfies`.
