# C-Abnahme, Frontend- und B4-Teil

Stand 2026-10-25, Branch `feat/c-karten`. Dieser Teil stammt vom Frontend-Builder (Karten, Orte-Tab, Navigation, PWA, EN). Die Belege für Backend, Pins
und Campus-Polygone stehen in `docs/C-PINS.md` und `docs/C-CAMPUS-OSM.md`, die der Tiles in `docs/TILES.md`.

## Gates

| Gate | Ergebnis |
|---|---|
| `npm run lint` | sauber |
| `npm run typecheck` (App und Specs) | sauber |
| `npx jest` | 223 Suites, 1804 Tests grün (1 übersprungen; der `it.todo` der EN-Parität ist durch 7 echte Tests ersetzt) |
| `npm run build` | grün; Initial 662,89 kB (173,86 kB übertragen), B3-Stand 654,33 kB: **+8,56 kB roh**, siehe Offen |
| `npm run check:map` | `map isolation ok`: kein `maplibre` und kein `pmtiles` in `index.html` oder im Initial-Bundle, `/map/maplibre-gl.mjs`, `-worker.mjs` und `.css` im Build, `geolocation` nur im Near-me-Chunk und im zone.js-Polyfill |
| `deploy/tiles-smoke.sh`, `smoke.sh` | gehören dem tiles-builder |

## Playwright (Wegwerf-nginx mit der Produktions-`nginx.conf` auf 8081, API und Worker des Dev-Stacks, Chromium aus nix)

`scripts/e2e-web.sh up 8081 dist/stupa-events/browser e2e/fixtures/tiles`, dann `E2E_BASE_URL=http://127.0.0.1:8081 npx playwright test --project=<projekt> <spec>`.

| Spec (Projekt) | Ergebnis | Inhalt |
|---|---|---|
| `map.spec.ts` (`map`, `channel: 'chromium'`) | 9 von 9 grün | T1 Netzwerk: nur die eigene Origin, kein `securitypolicyviolation`, kein `Set-Cookie`; T3 Cluster, Klick zoomt, Cluster an einem Ort filtert die Liste auf 12; T4 Gebäude 9 zeigt 3 in Tabelle und Liste; T5 In meiner Nähe sortiert, **kein Request mit Position** (URL und Body, nach dem Flug keine Anfrage), und ohne Erlaubnis der Hinweistext; T6 Position nach SPA-Navigation unter aktivem Service-Worker; T8 axe hell und dunkel bei 1280 und 390 px für `/karte` und `/campus`; T9 Handy |
| `venue-pin.spec.ts` (`map`) | 3 von 3 grün | T7: Klick setzt Pin und Zahlenfelder, "Adresse suchen" wird als `nominatim` gespeichert, privater Ort: Knopf aus, null Requests; axe auf dem Sheet; Anmeldung und Admin-API sind Route-Mocks |
| `offline.spec.ts` (`chromium`) | grün | Heute offline mit "Offline, Stand HH:MM", zuletzt geöffnetes Event offline lesbar, nie geöffnetes zeigt "Du bist offline." |
| `pwa-update.spec.ts` (`chromium`, Stack 8084) | grün | neuer Build: Prompt "Eine neue Version der App ist verfügbar." mit genau einem Knopf "Neu laden", Reload lädt die neue Version (`ngsw/state` ändert sich, `index.html` trägt die Marke); das Hash-Format von `ngsw.json` ist SHA-1 (40 Hex) |
| `en.spec.ts` (`chromium`) | 2 von 2 grün | Footer-Umschalter, `lang="en"`, Navigation, Überschriften, kein deutsches Wort in Kopf, Fuß und Navigation von sechs Seiten, Datum "Sun, 25 Oct 2026, 15:00 to 19:00", Wahl überlebt Neuladen, axe in EN, Browser mit `en-GB` startet englisch |
| `public.spec.ts`, `getstarted.spec.ts` (`chromium`) | 8 von 9 und 8 von 8 grün | Die Karte in der Navigation und die Handy-Leiste (Heute, Kalender, Karte, Abos) brechen nichts. Der Test "Angemeldete Person" scheitert am Keycloak-Login (nicht im Stack; wie B1-ABNAHME D), danach läuft der letzte Test der seriellen Datei nicht |

Die Karten-Specs mocken die Karten-API (`support/map-fixtures.ts`), damit die Zahlen vorhersagbar sind. Die Probe gegen die echte Karten-API und die echten Tiles steht aus, bis der Pin-Lauf (`docs/C-PINS.md`) gelaufen ist.

## Abnahmekriterien

- **C1** Karte lädt ohne Request an Dritte: `map.spec` T1. Range-Requests hinter nginx: `deploy/tiles-smoke.sh` (tiles-builder).
- **C2** (Frontend) kein Autocomplete und kein clientseitiger Nominatim-Aufruf: `grep -rn "nominatim\|openstreetmap.org" frontend/src` findet nur den Wert `nominatim` des Felds `geocodeSource` und Bezeichner, keine URL; der Aufruf geht über `POST /api/admin/venues/{id}/geocode`. Private Orte: Knopf aus und kein Request (`venue-pin.spec`, Jest `venue-pin-sheet.component.spec`).
- **C3** Weltkarte, Liste mit denselben Treffern, kein Request mit Koordinaten: `map.spec` T3 und T5, Jest `pages/map/map.component.spec`. Davos, Ischgl, Europapark und Straßburg stehen erst mit dem Pin-Lauf in den Daten.
- **C4** Gebäude 9 zählt korrekt in Karte, Tabelle und Liste: `map.spec` T4; keine OSM-Abfrage zur Laufzeit (T1).
- **B4** "Heute" offline lesbar: `offline.spec`. EN-Parität: `translations.spec` ("English parity", 7 Tests) und `en.spec`. Update-Prompt: `pwa-update.spec`.

## Abweichungen vom Kontrakt (Frontend)

1. **Icon**: das ui-kit hat kein `map`, die Navigation nutzt `pin`.
2. **Style-Pfade**: `style-light.json` und `style-dark.json` (Kontrakt), nicht `light.json` aus dem Auftrag.
3. **Handy-Liste**: auf dem Handy steht die Trefferliste unter der Karte (mit Sprunglink "Zur Liste springen"), nicht als Sheet von unten. Ab 900 px steht sie daneben.
4. **Campus-Detail**: die Gebäudeliste erscheint unter Karte und Tabelle (kein Seitenpanel), die Tabellenzeile "Anzeigen" ist die Tastaturalternative zum Klick auf die Fläche.
5. **Jahresauswahl** "Gab es": die letzten fünf Jahre statt einer Liste aus den Daten (die API liefert keine Jahre für die Karte).
6. **Flächenfarben** folgen der Token-Regel `token-roles.spec`: Füllungen mit `--color-accent`, `--color-accent-container` und `--color-on-accent-container`, nie mit `--color-primary`.
7. **Test-Tiles**: Reutlingen-Ausschnitt bis Zoom 10 (1,6 MB) statt Zoom 12 unter 1 MB; kleiner ging nicht, der Ausschnitt beginnt bei Zoom 7 und die tiefen Zoomstufen sind schon 1,4 MB. Zusammen 2,4 MB eingecheckt.
8. **EN-Kataloge** sind TS-Dateien mit `satisfies` (ein fehlender Schlüssel bricht den Build), nicht `en.json`.

## Bekannte Grenzen

- Die Server-Hülle `/e/<slug>` (Titel, Open Graph, JSON-LD) und die Texte aus der Datenbank (Kategorien, Interessen, Fachschaften, Einwilligungssatz) bleiben deutsch.
- Die interne Oberfläche bleibt deutsch; steht die Sprache auf Englisch, folgen dort nur Datumsformate.
- `/campus` markiert in der Navigation keinen Eintrag als aktuell (die Karte-Seite ist verlinkt über das Segment "Welt / Campus").
- Fehlende Glyphenbereiche (kyrillisch, arabisch) ergeben 404 für einzelne `.pbf`, die der `app-map` ignoriert.
