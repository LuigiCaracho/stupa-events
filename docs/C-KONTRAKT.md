# C-Kontrakt: Karten (C1 bis C4) und PWA/EN (B4)

Stand 2026-10-25, gelesen auf `feat/b3-abos` (HEAD `dd130b7`, Migration-Head `0012_purge_rearmed`, Frontend ohne Karte, nur Locale `de`). Der Branch `feat/c-karten` entsteht beim ersten Builder (tiles-builder, Commit 1) aus `feat/b3-abos`; alle Builder committen ihre Teile sofort mit dem Trailer

```
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013NodAsFyipzEwD8Nird4cT
```

Nichts pushen. Regeln wie bisher: Upstream-Konventionen, camelCase mit `extra=forbid`, Problem+JSON, tz-aware, Public-Routen ohne Cookie und nur über `events_public`, Angular standalone mit signals und ui-kit, Jest, Playwright, `PROVENANCE`, kleine Dateien, Kopf-Docstring, keine Trennkommentare. Code und Commits Englisch, UI Deutsch gegendert (Du-Form). Live-Systeme nie anfassen. Externe Downloads nur im Tile-Build-Skript und in der einmaligen Overpass-Prüfung (Abschnitt 4.6); der Nominatim-Lauf für die Bestandsorte läuft nur durch Luis (Abschnitt 4.7).

Quellen: PLAN 8.8, 9.1, 9.2, 11.2, 15.2 (P11, P12), 16.2 (B4), 16.3 (C1 bis C4); `lesen/extern.md` 2; ENTSCHEIDUNGEN (E30 Standort nur lokal). Alles, was ich gemessen oder im Paket gelesen habe, steht mit Beleg da; Annahmen sind als **Annahme** markiert und haben einen Test, der entscheidet.

## 0. Umfang

**Drin:** Tile-Pipeline (C1), Orte pflegen mit Pin, Geocoding auf Knopfdruck und Einmal-Pin der 44 Bestandsorte (C2), Weltkarte P11 (C3), Campuskarte P12 (C4), Orte-Tab in I23 mit Pin; B4: öffentliche `dataGroups`, Offline-Heute, Offline-Seite P14, iOS-Installationshinweis, `pwa-update.spec`, EN-Parität mit Sprachumschalter.

**Nicht drin:** Mini-Karte auf P04 und `GEO` im ICS (beides braucht eine weitere Allowlist-Entscheidung, Vorschlag in 9), Karte als Umschalter in P02, Tiles für Alpen und Süddeutschland über Zoom 5 hinaus (Vorschlag in 9), Offline-Karte, Push.

**Reihenfolge der Builder:** tiles-builder Commit 1 (Branch, Abhängigkeiten, Abschnitt 8) vor allen anderen; danach laufen backend, frontend und der Rest des tiles-builders parallel. Frontend braucht für `/karte` die API (Abschnitt 4) nur zum Verdrahten; bis dahin Jest mit Fixtures.

## 1. Lückenanalyse (Ist am Arbeitsbaum, Soll aus PLAN)

| # | Soll | Ist (Beleg) | Lücke und Maßnahme |
|---|---|---|---|
| L1 | Migration "0010" für Karten (Auftrag) | `backend/migrations/versions/` reicht bis `0012_purge_rearmed` (0010 bis 0012 gehören zu B3) | Neue Migration `0013_maps` (Abschnitt 3), `down_revision = "0012_purge_rearmed"` |
| L2 | `venue.lat/lon` | vorhanden: `Venue.lat/lon Numeric(9,6)`, Paar-CHECK `coordinates_pair`, Bereichs-CHECK, `geocode_source` (`pin|nominatim|import`), `geocoded_at` (`taxonomy/models.py`, Migration 0003) | keine Spalte neu; PATCH setzt heute immer `geocode_source=pin` (`admin/venues_router.py:_bookkeeping`), `nominatim` muss serverseitig prüfbar werden (4.4) |
| L3 | `public_precision exact|area|hidden` | vorhanden als `exact|building|hidden` (CHECK `ck_venue_public_precision`, Migration 0003; Admin-Labels "genau/Gebäude/verborgen") | **kein Umbenennen**: `building` ist das gemeinte `area`. Die Bedeutung wird erst jetzt wirksam: Koordinaten auf 3 Dezimalen gerundet (3.2). Abweichung 1 |
| L4 | Views geben Koordinaten aus | `public_event_v` hat `venue_name`, `venue_address`, `venue_city`, **keine** Koordinate und keine Gebäudenummer (`0007_event_dossier.py:_VIEW_BODY`); `public_venue_v` aus PLAN 8.1 gibt es nicht, `PublicVenue` hat `name,address,city` (`publicapi/schemas.py`) | `public_event_v` um `venue_lat`, `venue_lon`, `venue_geo_precision`, `venue_building_no` erweitern (3.2); Allowlist (`PUBLIC_VIEW_COLUMNS`, neue Modelle) und `LEFT_OUT` in `query/columns.py` nachziehen |
| L5 | Karten-API | keine `/api/public/map/*`, keine `/api/public/campus/*`; `/events` kennt `building` nicht (PLAN 8.5) | Abschnitt 4; `building` als Filter in `SiteFilters` und `/events` |
| L6 | Campus-Daten | keine Tabelle, kein Seed, `seeds/` kennt nur YAML (`checklists, dev_events, formats, interests`); `Venue.campus_building_no` ist nirgends befüllt oder gelesen | `campus_building` (3.3); Zuordnung Ort zu Gebäude über `venue.building_no` (steht im Seed aus dem Namen: `9-133`, `9-229`, `9-U09` ergeben `9`, `venue_reference.py:building_of`); `campus_building_no` bleibt ungenutzt (Abweichung 3) |
| L7 | Geocoding | kein Nominatim-Code; `httpx>=0.28` ist Abhängigkeit; `shared/ssrf.py:assert_allowed_url(url, allowlist=...)` vorhanden; `shared/ratelimit.RedisRateLimiter` ist **fail-open** (Docstring) | `geocode_cache` + Service + Endpunkt (4.4); der Limiter muss **fail-closed** sein, deshalb kein `RedisRateLimiter` (4.4) |
| L8 | Einmal-Pin der 44 Orte | Seed hat nur Adressen wo die Quelle sie nennt (M2-KONTRAKT 217): Pestalozzistraße 62 (2), 52, Alteburgstraße 150 (2), Alteburgstraße ohne Nr. (Texoversum), Ob. Gerberstraße 6 (ohne Ort), Gänsackerweg 2 Serfaus, Friedrich-Ebert-Straße 12 Reutlingen; Davos, Ischgl, Europapark, Straßburg haben **keine Adresse** | `scripts/pin_venues.py` (4.7). Widerspruch zwischen "hidden für ohne Adresse" und C3 "Davos, Ischgl, Europapark, Straßburg erscheinen": gelöst durch eine kuratierte Ortsliste (4.7), Weiche W-C1 |
| L9 | Tiles | keine; `/tiles/**` steht nur in `navigationUrls` und `ngsw-navigation.spec`; kein Volume, kein nginx-Block | Abschnitt 2 |
| L10 | MapLibre-Komponente | `app-map` fehlt in `shared/ui`; PLAN nennt "`maplibre-gl-csp`" | **Das Paket `maplibre-gl-csp` gibt es nicht** (`npm view maplibre-gl-csp` ergibt E404). `maplibre-gl@6.13.0` hat keinen getrennten CSP-Build mehr (Dateiliste in 2.5). Abweichung 2 |
| L11 | CSP `worker-src blob:` | `security-headers.conf`: `worker-src 'self'`; `Permissions-Policy: geolocation=()` | `blob:` ist laut Paketquelltext nicht nötig (2.5). `geolocation=(self)` ist nötig und muss global gelten (2.6); Abweichung 4 |
| L12 | Orte-Tab mit Pin | `venues.component.html`: Breite/Länge als `[disabled]="true"`, Spec erwartet disabled Spinbuttons; i18n `admin.coordinatesLater` "ab Stufe C" | I23 freischalten (5.4) |
| L13 | Public-Nav | `PUBLIC_NAV` = Heute, Suche, Kalender, Abos; PLAN 8.6: Heute (inkl. Suche), Kalender, Karte, Abos | `map` ergänzen, auf dem Handy `search` ausblenden (5.5) |
| L14 | `dataGroups` | `ngsw-config.json` hat nur `assetGroups` und `navigationUrls`; `/e/**` ist **ausgeschlossen** | B4 (5.6). Die öffentlichen Datenpfade heißen `/api/public/today` und `/api/public/events[/{slug}]` (`site_router.py`), nicht `/events*` allein |
| L15 | Offline-Heute | `OfflinePageComponent` und Route `/offline` existieren, aber nichts navigiert dorthin; `today.component` kennt kein Offline und kein "Stand" (`grep -i offline` in `pages/today`: leer) | Zustand "Offline, Stand HH:MM" in P01, P14 real erreichbar (5.6) |
| L16 | Lazy Chunks im Precache | `ngsw-config.json`: Gruppe `app` hat `installMode: prefetch` mit `/*.js`; das schließt **alle** Lazy-Chunks im Wurzelverzeichnis ein | MapLibre (1,08 MB roh, 286 KB gzip) darf nicht auf jedem Erstbesuch vorgeladen werden: Laden als Asset unter `/map/` (2.5) |
| L17 | iOS-Hinweis | `core/browser/installed-app.token.ts` erkennt den Standalone-Modus (inkl. `navigator.standalone`); kein Hinweis-Baustein | `app-install-hint` (5.6) |
| L18 | Update-Prompt-E2E | `core/pwa/sw-update.service.ts` kopiert, Specs Jest; `frontend/e2e/` hat kein `pwa-update.spec.ts` | 5.6, 6.4 |
| L19 | EN | `Locale = 'de'`, `SUPPORTED_LOCALES = ['de']`, `FORMAT_LOCALES = {de}`; `translations.spec.ts` hat `it.todo('has an en entry for every de key')`; kein Umschalter im Footer | 5.7 (rund 260 Schlüssel plus Karte; interne Kataloge bleiben DE) |
| L20 | WebGL im E2E | Playwrights Standard-Browser `chromium_headless_shell` (nix, Revision 1243) liefert **kein** WebGL (`getContext('webgl2')` ergibt `null`, gemessen mit und ohne SwiftShader-Flags); `channel: 'chromium'` (neuer Headless-Modus) liefert `WebGL 2.0 (OpenGL ES 3.0 Chromium)` ohne Flags | eigenes Playwright-Projekt `map` mit `channel: 'chromium'` (6.1) |
| L21 | `.mjs` hinter nginx | `nginx:1.27-alpine` (1.27.5) hat in `/etc/nginx/mime.types` nur `application/javascript js;` (gemessen), `.mjs` käme als `application/octet-stream`; Modul-Worker brauchen einen JavaScript-MIME-Typ | `types { text/javascript mjs; }` in der `/map/`-Location (2.6) |
| L22 | Weitere Fallen | PMTiles-Archive sind intern gzip-komprimiert; `pmtiles`-JS verlangt `Content-Length` und ignoriert schwache ETags (`W/`, gelesen in `pmtiles@4.5.0` `FetchSource.getBytes`) | `/tiles/` ohne `gzip`, Dateien statisch (2.6) |

## 2. Tile-Pipeline (C1)

### 2.1 Quellen und Messwerte (am 2026-10-25 gemessen)

| Baustein | Festlegung | Beleg |
|---|---|---|
| Basiskarte | Protomaps Daily Build `https://build.protomaps.com/20261024.pmtiles` (Planet, 139 134 051 681 Byte, `Accept-Ranges: bytes`, Cloudflare), Schema Protomaps Basemap v4.15.2, OSM-Stand 2026-10-24 04:00 UTC | `curl -I`; `pmtiles show` des Extrakts (`version 4.15.2`, `planetiler:osm:osmosisreplicationtime`) |
| Aufbewahrung | Der Bucket hält die Builds der **letzten Woche** und je Patchversion den neuesten; der Link `20261024` stirbt also um den 2026-10-31 | docs.protomaps.com/basemaps/downloads |
| CLI | `pmtiles` 1.31.2: nixpkgs-Attribut `pmtiles` (Version 1.31.2, mcp-nixos), Release `protomaps/go-pmtiles` v1.31.2, Asset `go-pmtiles_1.31.2_Linux_x86_64.tar.gz` | `nix build nixpkgs#pmtiles`, `gh api repos/protomaps/go-pmtiles/releases/latest` |
| Welt | `pmtiles extract <build> world.pmtiles --maxzoom=5` | 15 048 644 Byte, SHA-256 `46a7581e8d42770a4d84006c2520ddb7113b91e41c3a65f79a7530fc5dda7148` |
| Region Reutlingen | `pmtiles extract <build> reutlingen.pmtiles --bbox=9.05,48.40,9.35,48.58 --maxzoom=15` | 17 469 543 Byte, SHA-256 `73b3b4e944c820090f71de37042b79914bd995ad5397f6f60d8c44290a83ac59`, Bounds exakt wie angefragt, Zoom 0 bis 15, 1079 Kacheln |
| Determinismus | zwei Läufe hintereinander ergeben **dieselben** SHA-256 | gemessen |
| Gesamt | 32,5 MB, Dauer rund 2 min (Region 40 bis 90 s, Welt 2 bis 25 s) | gemessen |
| Zoomgrenzen | Protomaps liefert bis Zoom 15; MapLibre vergrößert darüber (Karte `maxZoom` 18) | `pmtiles show` (max zoom 15) |
| Alternativgrößen (Trockenlauf `--dry-run`) | Welt bis Zoom 6: 45 MB, bis 7: 189 MB; SW-Deutschland und Alpen (`6.0,46.4,11.0,49.2`) bis Zoom 9: 18 MB, bis 10: 41 MB, bis 11: 86 MB | gemessen, nicht gebaut |
| Attribution | "© OpenStreetMap" (ODbL, Produced Work), steht in den Archiv-Metadaten (`attribution`) und bleibt sichtbar | docs.protomaps.com |

Weil nur die Region bis Zoom 15 reicht, zeigt die Weltkarte außerhalb Reutlingens nur Zoom-5-Detail (Länder, Großstädte). Das reicht für Pins auf Alpen und Europapark im Maßstab "wo gab es was"; ein feineres Band ist Weiche W-C2.

### 2.2 `scripts/build-tiles.sh` (Besitz tiles-builder)

Reines Bash, `set -euo pipefail`, Kopf-Docstring. Alle externen Zugriffe des Projekts außer Abschnitt 4.6 stehen hier. Die Pins stehen in der Datei `deploy/tiles.lock` (versioniert, kein Binärartefakt):

```
PMTILES_VERSION=1.31.2
PROTOMAPS_BUILD=20261024
PROTOMAPS_URL=https://build.protomaps.com/${PROTOMAPS_BUILD}.pmtiles
WORLD_MAXZOOM=5
REGION_NAME=reutlingen
REGION_BBOX=9.05,48.40,9.35,48.58
REGION_MAXZOOM=15
WORLD_SHA256=46a7581e...7148
REGION_SHA256=73b3b4e9...ac59
ASSETS_REPO=protomaps/basemaps-assets
ASSETS_COMMIT=028c18f713baecad011301ff7a69acc39bcc2ae7
```

| Modus | Wirkung |
|---|---|
| `fetch` (Standard) | findet `pmtiles` (PATH, sonst `nix run nixpkgs#pmtiles`, sonst gepinntes Release-Binary mit SHA-256 in `tiles.lock`), prüft `pmtiles --help`-Version gegen `PMTILES_VERSION`, extrahiert nach `deploy/tiles/world.pmtiles` und `deploy/tiles/reutlingen.pmtiles` über `.part`-Dateien, `pmtiles verify`, vergleicht SHA-256 mit `tiles.lock` und benennt erst dann um. Bei Abweichung bricht es ab und löscht die `.part`-Datei. Fehlt der Build (HTTP 404 nach Ablauf der Woche), steht im Fehlertext "Build abgelaufen: `bump`" |
| `bump <YYYYMMDD>` | schreibt neuen Build und neue Prüfsummen in `tiles.lock`, zeigt die Differenz der Größen; der Diff geht durch Review (Prüfsummen ändern sich mit jedem Build) |
| `verify` | prüft die Dateien in `deploy/tiles/` oder im Volume gegen `tiles.lock` (offline) |
| `install` | kopiert nach `tiles_data` über einen Wegwerf-Container (`docker run --rm -v <projekt>_tiles_data:/t -v $PWD/deploy/tiles:/src:ro alpine sh -c 'cp /src/*.pmtiles /t/'`), danach `verify` im Volume |
| `assets` | lädt `ASSETS_REPO` am `ASSETS_COMMIT` als Tarball, prüft den SHA-256 (im Lauf zu pinnen und in `tiles.lock` einzutragen), kopiert die in 2.4 genannten Dateien nach `frontend/public/map-style/` |

`deploy/tiles/` ist in `.gitignore` (Tiles nicht ins Git). `docs/TILES.md` beschreibt Aufruf, Ablauf nach Ablauf der Woche, Lizenzen und die Pflege (Besitz tiles-builder). Der Download ist **nur** hier; Tests und CI laden nie Tiles (CI-Job `fe-unit` und `compose-smoke` nutzen die Test-Fixture aus 6.1).

### 2.3 Style (hell und dunkel)

- Die Layer kommen aus `@protomaps/basemaps@5.7.2` (BSD-3, `layers(source, flavor, {lang: 'de'})`, `namedFlavor('light'|'dark')`, gelesen in `src/index.ts`). Ein Generator `scripts/gen-map-style.mjs` (tiles-builder) schreibt **eingecheckte** Dateien `frontend/public/map-style/style-light.json` und `style-dark.json`. Sie enthalten nur die Basiskarte; Pins, Cluster und Gebäudeflächen setzt `app-map` zur Laufzeit, weil sie Farben aus den Design-Tokens brauchen.
- Zwei Quellen: `world` (`pmtiles:///tiles/world.pmtiles`, `maxzoom 5`) und `region` (`pmtiles:///tiles/reutlingen.pmtiles`, `maxzoom 15`). Der Generator ruft `layers()` zweimal auf. Regel: Weltlayer ohne Beschriftung gelten für alle Zoomstufen (Überzoom über 5), Weltbeschriftungen nur bis Zoom 7; Regionslayer ab Zoom 7. So gibt es keine doppelten Labels. Das Aussehen prüft der Builder mit Screenshots (hell und dunkel, Zoom 3, 7, 12, 16 bei Reutlingen und Davos) und legt sie in `docs/TILES.md`.
- `glyphs`: `/map-style/fonts/{fontstack}/{range}.pbf`, `sprite`: `/map-style/sprites/v4/light` bzw. `/dark` (MapLibre hängt `.json`, `.png`, `@2x` an). Beides same-origin.
- Akzent-, Pin- und Flächenfarben liest `app-map` per `getComputedStyle` aus den Tokens (`--color-primary` u. a.) beim Start und beim Wechsel von `ThemeService.resolved`.

### 2.4 Glyphen und Sprites lokal

Quelle `protomaps/basemaps-assets` am Commit `028c18f713baecad011301ff7a69acc39bcc2ae7` (2025-10-31); Schriften unter SIL OFL (`fonts/OFL.txt` liegt im Repo, wird mitkopiert). Der Style braucht `Noto Sans Regular`, `Noto Sans Medium`, `Noto Sans Italic`. Kopiert werden pro Schrift **nur** die Bereiche `0-255`, `256-511`, `7680-7935`, `8192-8447`, `8448-8703` (Latein inkl. Umlaute, Satzzeichen, Euro; zum Beispiel `Noto Sans Regular/0-255.pbf` 76 044 Byte, `8192-8447.pbf` 64 220 Byte) plus `sprites/v4/light|dark{,@2x}.{json,png}` (`light.png` 16 174 Byte, `@2x` 28 852 Byte). Beides wird eingecheckt (rund 3 MB) mit Eintrag in `PROVENANCE.map-assets.json` (Quelle, Commit, Lizenz). Fehlende Bereiche (kyrillische oder arabische Namen auf der Weltkarte) ergeben 404 für einzelne `.pbf`; `app-map` ignoriert Glyph-Fehler im `error`-Handler, die Netzwerk-Allowlist zählt nur Fremd-Origins.

### 2.5 MapLibre und PMTiles in Angular

- Versionen (gepinnt, exakt, kein `^`): `maplibre-gl@6.13.0` (veröffentlicht 2026-10-06, also 19 Tage alt; 6.14.0 vom 2026-10-11 ist nur 14 Tage alt, 6.15.0 vom 2026-10-18 zu neu), `pmtiles@4.5.0` (2026-08-10), dev: `@protomaps/basemaps@5.7.2` (2026-03-10). Lizenzen BSD-3-Clause (alle drei, `package.json`).
- `maplibre-gl@6.13.0` ist **reines ESM** (`exports` nur `import`), hat **keinen** CSP-Build. Der Worker ist die Datei `dist/maplibre-gl-worker.mjs` (508 KB roh, 144 KB gzip). Aus dem Paketquelltext (`dist/maplibre-gl.mjs`, Funktionen zur Worker-Erzeugung): Ist die Worker-URL **same-origin**, ruft MapLibre `new Worker(url, {type: 'module'})` direkt auf; **nur bei fremder Origin** baut es einen `blob:`-Worker. Damit genügt `worker-src 'self'`. `setWorkerUrl(url)` ist exportiert. Eine statische Suche nach `eval(` und `new Function` in `maplibre-gl.mjs` und `maplibre-gl-worker.mjs` fand nichts (`unsafe-eval` ist nicht nötig). Das **beweist der Test 6.1** zur Laufzeit (kein `securitypolicyviolation`); bis dahin gilt es als Befund aus dem Quelltext.
- Laden als Asset, nicht als Chunk (L16): `angular.json` kopiert `node_modules/maplibre-gl/dist/maplibre-gl.mjs`, `maplibre-gl-worker.mjs`, `maplibre-gl-shared.mjs` und `maplibre-gl.css` nach `/map/`. `MapLoaderService` (`shared/ui/map/map-loader.service.ts`) lädt einmal per `import(/* webpackIgnore */ '/map/maplibre-gl.mjs?v=6.13.0')` über eine Variable (damit esbuild den Specifier nicht bündelt), setzt `setWorkerUrl('/map/maplibre-gl-worker.mjs?v=6.13.0')`, registriert `addProtocol('pmtiles', protocol.tile)` mit `pmtiles` aus dem normal gebündelten Karten-Chunk und gibt die Typen über `import type` aus `maplibre-gl`. Das CSS lädt `app-map` per `<link rel="stylesheet" href="/map/maplibre-gl.css">` einmalig. **Annahme:** esbuild des Angular-Application-Builders lässt einen Variablen-`import()` unangetastet. Der Builder prüft das mit `npm run build` und `grep` im `dist`; scheitert es, ist die Rückfallebene der normale Chunk und die Messung der Vorladegröße (Abweichung 5).
- Der Karten-Chunk (`app-map`, PMTiles-Protokoll) wird nur von den Routen `/karte`, `/campus` und vom Orte-Tab (`@defer`) geladen. `scripts/check-map-isolation.cjs` (frontend) prüft im `dist`, dass `maplibre` weder im `index.html` noch im Initial-Bundle vorkommt, und läuft im Job `fe-unit`.
- PMTiles-Quellen holen die Datei per `fetch` mit `Range`. `FetchSource` setzt `Headers` pro Quelle: `app-map` übergibt `ngsw-bypass: true` (dokumentierter Bypass des Angular-Service-Workers) zusätzlich zur Ausnahme in 2.8.
- Dev (`ng serve`): `/map/*` kommt aus den `assets`; `/tiles` über den Dev-Proxy (2.7).

### 2.6 nginx (`deploy/web/nginx.conf`, `security-headers.conf`)

```
map $uri $ev_cache_control {
    ...
    ~^/tiles/          "public, max-age=3600";
    ~^/map-style/      "public, max-age=86400";   # vor der Endungsregel
    ...
}

location ^~ /tiles/ {
    include /etc/nginx/snippets/security-headers.conf;
    alias /usr/share/nginx/tiles/;
    limit_except GET HEAD { deny all; }
    limit_req zone=ev_tiles burst=200 nodelay;     # limit_req_zone ... zone=ev_tiles:10m rate=50r/s
    gzip off;
    access_log off;
    add_header Accept-Ranges bytes always;
    try_files $uri =404;
}

location ^~ /map/ {
    include /etc/nginx/snippets/security-headers.conf;
    types { text/javascript mjs; text/css css; }
    try_files $uri =404;
}
```

- `/tiles/`: statische Dateien, nginx beantwortet `Range` (206, `Content-Range`) selbst; **kein** `gzip` (die Archive sind intern gzip, ein schwaches ETag oder `Content-Encoding` bräche `pmtiles`, L22); `access_log off`, weil jede Kachel eine Anfrage ist und Logs sonst fluten (die Pfade enthalten keine Personendaten). Der ETag ist stark (Standard für statische Dateien), `pmtiles` erkennt Dateiwechsel darüber und lädt neu (`EtagMismatch` im Quelltext).
- `Cache-Control` über die vorhandene Map `$ev_cache_control`, damit `security-headers.conf` den Header genau einmal setzt (smoke prüft das).
- `/map/` mit eigenem `types`-Block (L21). `/map-style/` und `/karte`, `/campus` laufen über den SPA-Fallback `location /` (kein neuer Block, `include security-headers.conf` ist dort schon).
- **CSP**: bleibt unverändert `worker-src 'self'` (2.5). **Permissions-Policy**: `geolocation=(self)` statt `geolocation=()`, **global in `security-headers.conf`**. Begründung: Die Richtlinie gilt je Dokument beim Laden; nach einem SPA-Wechsel von `/` nach `/karte` bleibt die Richtlinie des Dokuments `/`, und der Service-Worker liefert Navigationen aus dem zwischengespeicherten `index.html` samt dessen Headern. Eine Richtlinie nur für `/karte` und `/campus` griffe damit nur bei einem Kaltstart auf diesen Pfaden (**Annahme**, der Test 6.1 "geolocation per SPA-Navigation" entscheidet). `geolocation=(self)` erlaubt nur Code der eigenen Origin; es gibt genau einen Aufrufer (`NearMeService`), und `connect-src 'self'` verhindert Abfluss. Ein Test sucht im gebauten Bundle nach `geolocation` und lässt nur diese Datei zu. Rückfallebene, falls der Test zeigt, dass `blob:` doch nötig ist: Map `$ev_csp` nach `$uri` (`/karte`, `/campus`) und Links dorthin als Dokument-Navigation (`<a href>` mit `ngsw-bypass`); das ist Plan B und wird nur gebaut, wenn Plan A scheitert.
- `deploy/smoke.sh` bekommt `/karte`, `/campus`, `/tiles/world.pmtiles`, `/map/maplibre-gl-worker.mjs`, `/map-style/style-light.json`; Zahl der Locations im Output steigt entsprechend.

### 2.7 Compose und Dev

- `docker-compose.yml`: Volume `tiles_data`; `web` mountet `tiles_data:/usr/share/nginx/tiles:ro`; `deploy/web/Dockerfile` legt das Verzeichnis an (`RUN mkdir -p /usr/share/nginx/tiles`). `compose-lint.sh` prüft: `web` mountet `tiles_data` read-only.
- `docker-compose.dev.yml`: Dienst `tiles` (`nginx:alpine`, bindet `deploy/tiles` nach `/usr/share/nginx/html/tiles`, Port `127.0.0.1:8083`). `frontend/proxy.conf.json` bekommt `/tiles` nach `http://localhost:8083` (Range läuft durch den Proxy).
- `deploy/dev-up.sh` startet den Dienst; fehlen die Dateien, druckt es einen Hinweis auf `scripts/build-tiles.sh`.
- Sicherung: `tiles_data` ist reproduzierbar, solange der gepinnte Build lebt (eine Woche); danach nur noch aus Kopie. Die beiden Dateien (32,5 MB) gehören in den Umfang von `backup.sh` (Weiche W-C3).

### 2.8 Service-Worker-Ausnahme

`ngsw-config.json`: `/tiles/**` bleibt in `navigationUrls` ausgeschlossen (steht schon) und es gibt **keine** `dataGroup` und keine `assetGroup`, die `/tiles` trifft; Pfade außerhalb jeder Gruppe reicht der Worker unverändert durch. Zusätzlich `ngsw-bypass` (2.5). `/map/**` ist ebenfalls in keiner Gruppe (nicht vorgeladen); die Sprite-PNGs unter `/map-style/` trifft die vorhandene Gruppe `assets` (lazy), das ist gewollt und klein. `ngsw-navigation.spec.ts` und `ngsw-assets.spec.ts` bekommen die neuen Zusicherungen (6.3).

## 3. Datenmodell: Migration `0013_maps`

`revision = "0013_maps"`, `down_revision = "0012_purge_rearmed"`, genau ein Head, additiv, `downgrade()` stellt die Views der Migration 0008 wieder her (Muster wie 0008: View droppen und neu anlegen, Postgres kann Spalten nicht per `CREATE OR REPLACE` entfernen).

### 3.1 Tabellen

**`geocode_cache`**: `query_hash text PRIMARY KEY` (SHA-256 der normalisierten Anfrage), `query_norm text NOT NULL` (klein, Leerraum zusammengefasst; enthält nur Adress- oder Ortsnamen), `found boolean NOT NULL`, `lat numeric(9,6)`, `lon numeric(9,6)`, `display_name text`, `osm_type text`, `osm_id bigint`, `fetched_at timestamptz NOT NULL`. CHECK: `found = (lat IS NOT NULL AND lon IS NOT NULL)`, `query_norm !~ CONTROL_CHARS`, Länge höchstens 300. Ein Treffer ist 180 Tage gültig, ein Nichttreffer 30 Tage (negatives Caching gegen Wiederholung; die Policy sperrt wiederholte gleiche Anfragen). Rechte: `events_app` SELECT/INSERT/UPDATE (Standard), `DELETE` nur für den Ablauf-Job (Liste in `roles.sql` und `test_db_grants.py`); `events_public` und `events_subs` nichts.

**`campus_building`**: `number text PRIMARY KEY` (`^[0-9]{1,3}[a-z]?$`), `name text NOT NULL`, `geometry jsonb NOT NULL` (GeoJSON `Polygon` oder `MultiPolygon`, WGS84, Koordinaten auf 6 Dezimalen), `approx boolean NOT NULL DEFAULT false`, `osm_ref text` (z. B. `way/123456`), `sort int NOT NULL DEFAULT 0`. CHECKs: `geometry ->> 'type' IN ('Polygon','MultiPolygon')`, `NOT approx OR osm_ref IS NULL`. **Keine** Spalte `venue_ids` (Abweichung 3): der Zusammenhang Ort zu Gebäude ist `venue.building_no = campus_building.number` und bleibt so an einer Stelle.

Befüllt aus `backend/seeds/campus.geojson` (4.6) durch `app/modules/taxonomy/campus.py:seed_campus()` (idempotent per `number`, nur `INSERT ... ON CONFLICT DO NOTHING`), aufgerufen von der Migration und von `seed_dev.py`. Ein Hash-Test pinnt die Datei wie bei `test_reference_data.py`; spätere Polygonkorrekturen sind eine neue Migration.

### 3.2 View-Erweiterung `public_event_v`

Vier Spalten am Ende (`CREATE OR REPLACE VIEW` genügt), Ausdrücke im selben `_VIEW_BODY`-Stil wie `0007`:

```sql
CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.lat IS NOT NULL
          AND v.public_precision = 'exact'    THEN v.lat::float8
     WHEN v.id IS NOT NULL AND NOT v.is_private AND v.lat IS NOT NULL
          AND v.public_precision = 'building' THEN round(v.lat, 3)::float8 END AS venue_lat,
-- venue_lon analog mit v.lon
CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.lat IS NOT NULL
          AND v.public_precision <> 'hidden' THEN v.public_precision END AS venue_geo_precision,
CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.public_precision <> 'hidden'
     THEN v.building_no END AS venue_building_no
```

- Das **Runden passiert im View**, einer einzigen Stelle; Python rundet nie und liest nie die Rohkoordinate. `round(numeric, 3)` heißt rund 111 m in Nord-Süd-Richtung, rund 75 m in Ost-West bei Reutlingen.
- Freie Orte (`venue_text`, kein `venue_id`) bekommen nie Koordinaten (`geo_override` gibt es im Modell nicht; `grep geo_override backend/app` ist leer). Private Orte: weder Koordinate noch Gebäudenummer.
- `events_public` und `events_subs` behalten ihre Rechte (Grant auf den View, kein neues Objekt).
- **Neuer View `public_campus_building_v`** (`number, name, geometry, approx, sort`): `roles.sql` gewährt `events_public` Zugriff automatisch über das Muster `public\_%\_v`; kein Eingriff in `roles.sql` nötig, nur der Test `test_db_grants_roles_sql.py` bekommt den Namen.
- Allowlist: `PUBLIC_VIEW_COLUMNS` um die vier Spalten; `query/columns.py:LEFT_OUT` um dieselben (Karten und Listen lesen sie nicht); neue Modelle in `PUBLIC_FIELDS` (4.1). `allowlist.py` hat ein CODEOWNERS-Review.
- `PublicVenue` und der Feed (`feed-v2.json`) bleiben **unverändert** (keine Koordinate im Feed in C, Abweichung 6).

### 3.3 Index und Ablauf

Index `venue(building_no) WHERE building_no IS NOT NULL` ist nicht nötig (44 Zeilen). Der Ablauf-Job für `geocode_cache` (Treffer 180 Tage, Nichttreffer 30 Tage) hängt am vorhandenen täglichen Purge-Cron im Worker.

## 4. API

Alle öffentlichen Routen in `app/modules/publicapi/map_router.py` (neu, Include in `api_routers.py` neben `site_router`), gleiche Mechanik wie `site_router`: `respcache.serve` (Redis-Kopie je Feed-Version, `ETag`, 304, Rate-Limit nur bei Miss), `TTL = 60`, `Cache-Control: SWR`, `events_public`-Session, kein Cookie. Unbekannte Parameter werden ignoriert. Antworten als GeoJSON (`application/geo+json` ist unnötig streng für Angular; Antwort `application/json`).

### 4.1 `GET /api/public/map/events`

Parameter: `from`, `to` (Tage `YYYY-MM-DD`, Berliner Tag, wie `/events`), `past` (bool), `category` (Slugs, bis 10), `organization`, `bbox=minLon,minLat,maxLon,maxLat` (vier Zahlen, Längen -180 bis 180, Breiten -90 bis 90, `min < max`), `limit` (1 bis 2000, Standard 1000). Ohne `from`/`to`: `past=0` ergibt ab jetzt (laufende und kommende), `past=1` Vergangenes, neueste zuerst. Filter über `SiteFilters` (gleiche Zeitsemantik wie P01), zusätzlich `venue_lat IS NOT NULL`. Hinweis: Das Web-UI sendet **nie** `bbox` (5.2, E30); der Parameter ist für andere Leser da.

```json
{ "type": "FeatureCollection", "generatedAt": "...", "truncated": false,
  "features": [ { "type": "Feature",
    "geometry": { "type": "Point", "coordinates": [9.187, 48.482] },
    "properties": { "slug": "...", "title": "...", "startsAt": "...", "endsAt": "...",
      "status": "scheduled", "categorySlug": "kino", "imageThumb": "/api/public/media/<id>.webp" | null,
      "venueName": "Kinosaal 9-133", "precision": "building" } } ] }
```

Pydantic-Modelle `PublicMapCollection`, `PublicMapFeature`, `PublicPoint`, `PublicMapProperties` (camelCase, `extra=forbid`), alle in `PUBLIC_FIELDS`; Schema-Datei `tests/schema/public-map-v1.json` als Vertrag. Koordinaten kommen als `float` aus dem View (Reihenfolge Länge, Breite nach GeoJSON). Abgesagte Events erscheinen mit `status: cancelled` (die UI streicht sie durch).

### 4.2 `GET /api/public/campus/buildings`

Parameter `from`, `to` (Standard: der heutige Berliner Tag), Antwort `FeatureCollection` aus `public_campus_building_v` mit `geometry` unverändert und `properties {buildingNo, name, approx, count}`. `count` = Anzahl öffentlicher Events mit `venue_building_no = number`, Zeitüberlappung nach `SiteFilters`, `public_status <> 'cancelled'` (Abgesagte zählen nicht als "viel los"). Gebäude ohne Events haben `count: 0` und erscheinen trotzdem. Modelle `PublicCampusCollection`, `PublicCampusFeature`, `PublicCampusProperties`.

### 4.3 `GET /api/public/campus/events?building=<nr>&from&to&limit&cursor`

Dünne Hülle um `/api/public/events` mit dem neuen Filter `building` (Muster `^[0-9]{1,3}[a-z]?$`, in `SiteFilters` als `venue_building_no = :b`); dieselbe Antwort `PublicSearchOut`, `limit ≤ 50`. `building` ist zusätzlich ein Parameter von `/api/public/events` (PLAN 8.5). Unbekannte Gebäudenummer: 404 (wie jede unbekannte Ressource), keine Unterscheidung zu "keine Events" (die Liste ist leer, 200).

### 4.4 Admin: Geocoding und Pin

- `PATCH /api/admin/venues/{id}`: `lat`, `lon`, `publicPrecision` (gibt es). Neu: optionales `geocodeSource ∈ {pin, nominatim}`. `nominatim` nimmt der Server nur an, wenn `(lat, lon)` auf 1e-6 mit dem Cache-Treffer der aktuellen Adressanfrage des Ortes übereinstimmt (4.4.2); sonst wird `pin` gesetzt. `exact` oder `building` ohne Koordinate und ohne `building_no` ergibt 422 `coordinates_missing`. Ein privater Ort bekommt nie `geocode_source = nominatim`.
- `POST /api/admin/venues/{id}/geocode` (Recht `venue.manage`, Body leer): Ablauf
  1. Ort laden; `is_private` ergibt 422 `venue_private` ("Private Orte werden nicht extern gesucht.") **vor** jedem Netzzugriff.
  2. Anfrage aus Adresse, PLZ und Ort bilden (`address` und `city` Pflicht, sonst 422 `address_incomplete`); normalisieren; SHA-256.
  3. `geocode_cache` lesen; Treffer im Gültigkeitsfenster: Antwort ohne Netz (`cached: true`).
  4. Sonst globale Sperre: Redis `SET events:geocode:lock 1 NX PX 2000`; schlägt es fehl, Antwort 429 `geocode_rate` mit `Retry-After`; ist **Redis nicht erreichbar, Antwort 503** (fail-closed, anders als `RedisRateLimiter`, L7). Danach ein einziger `httpx.AsyncClient`-Aufruf `GET {NOMINATIM_BASE_URL}/search?q=...&format=jsonv2&limit=1`, `follow_redirects=False`, Timeout 5 s, Header `User-Agent: STUPA-Events/<app_version> (+https://events.reutlingen.university; <NOMINATIM_CONTACT>)`, Ziel über `assert_allowed_url` mit Allowlist `nominatim.openstreetmap.org`.
  5. Ergebnis (auch "nichts gefunden") in `geocode_cache` schreiben. Antwort `{found, lat, lon, displayName, cached, attribution: "© OpenStreetMap"}`; **es wird nichts am Ort gespeichert**, die Redaktion übernimmt per PATCH.
  6. Audit-Eintrag `venue.geocode` (nur Ort-ID und `found`, keine Adresse).
- Einstellungen in `Settings`: `nominatim_enabled: bool = False`, `nominatim_base_url`, `nominatim_contact` (Pflicht, wenn aktiv); `.env.host.example` ergänzen. Ist es aus: 503 `geocode_disabled`.
- Kein Autocomplete, kein clientseitiger Aufruf, kein Aufruf im Worker.

### 4.5 Rechte, Rate-Limits, Cache

Öffentlich: `public_limit` wie `/events`; nginx `/api/public/` greift schon. Admin: `venue.manage` wie bisher. Redis-Version `events:feed:version` wird bei Orts- oder Pinänderung bereits über `invalidate_feed` erhöht (`patch_venue`), damit Karten-Antworten nicht veralten.

### 4.6 Campus-Polygone: Overpass-Prüfschritt (einmalig, Besitz backend)

1. **Eine** Anfrage an `https://overpass-api.de/api/interpreter` (POST, eigener User-Agent), Entwurf (Syntax der Builder gegen die Overpass-Doku prüfen; Anker sind die Adressen, die der Seed nennt: Alteburgstraße 150, Pestalozzistraße 52 und 62, denn Gebäude 9 liegt laut Seed an der Pestalozzistraße 62):
   ```
   [out:json][timeout:60];
   ( nwr["addr:street"="Alteburgstraße"]["addr:housenumber"="150"];
     nwr["addr:street"="Pestalozzistraße"]["addr:housenumber"~"^(52|62)$"]; )->.anchor;
   ( way(around.anchor:400)["building"]; relation(around.anchor:400)["building"]; );
   out geom tags;
   ```
   Timeout oder 5xx: einmal nach 5 Minuten wiederholen, dann abbrechen und melden (die Erfahrung aus `extern.md` 2.5: frühere Abfragen scheiterten mit 502/504).
2. Zuordnung Nummer zu Umriss nur über Tags (`ref`, `name`, `building:ref`, `addr:housenumber` mit "Gebäude N") oder über einen Anker (Adresspunkt des Ortes aus dem Seed liegt im Umriss). **Nie raten.** Ergebnis `backend/seeds/campus.geojson` (FeatureCollection, `properties {number, name, osmRef}`), Attribution und Abfragezeit in `docs/C-CAMPUS-OSM.md` (Tabelle: Gebäude 1, 3, 5, 6, 9, 17, 30 und weitere gefundene; Spalte "Quelle: OSM-Tag / Anker / fehlt").
3. **Gebäude 9 ist Pflicht** (C4). Findet der Builder es nicht eindeutig, stoppt er und meldet es. Fehlende andere Gebäude bleiben fehlend und stehen in der Tabelle; Handpolygone (`approx: true`) braucht Koordinaten, die der Builder offline nicht ermitteln kann (kein Luftbild-Zugriff): Weiche W-C4. Eine bloße Nachzeichnung aus OSM-Umrissen ist ohnehin ODbL-abgeleitet; Attribution "© OpenStreetMap-Mitwirkende" steht im Fuß der Campuskarte und in `docs/C-CAMPUS-OSM.md` (Share-Alike-Frage für die abgeleitete Datenbank: nicht geprüft, Hinweis an Luis).
4. Keine OSM-Abhängigkeit zur Laufzeit: die API liest nur `campus_building`.

### 4.7 `backend/scripts/pin_venues.py` (Einmal-Skript)

Standard ist **Trockenlauf** (kein Netz, schreibt nichts, druckt den Plan), `--apply` schreibt, `--live` erlaubt Nominatim. Reihenfolge je Ort (nur aktive, nicht private; privat wird übersprungen und gemeldet):

1. **Campusorte** (`building_no` hat ein Polygon in `campus_building`): `lat/lon` = Flächenschwerpunkt des Polygons (reine Python-Rechnung, 6 Dezimalen), `geocode_source = import`, `public_precision = building`. Das deckt Kinosaal 9-133, Maker Space 9-229, FSI 9-U09 und die anderen Räume ohne Netz ab.
2. **Orte mit Adresse und Ort** (Pestalozzistraße 52/62, Alteburgstraße 150, Serfaus, Rosengarten): über denselben Service wie 4.4 (Cache, 2-s-Abstand, Nominatim, `--live`), `geocode_source = nominatim`, `public_precision = building`.
3. **Kuratierte Zielorte** `PLACE_QUERIES` im Skript (Weiche W-C1, zur Freigabe durch Luis): `davos` = "Davos", `ischgl` = "Ischgl", `europapark` = "Europa-Park, Rust", `strassburg` = "Straßburg", `montafon`, `flumserberg`, `serfaus-fiss-ladis`; ausdrücklich **nicht** `schwarzwald` (Region), `arosa-lenzerheide` (zwei Orte), Clubs ohne Ort. Sie sind Ortsnamen, keine Adressen; Präzision `building`.
4. Alle übrigen bleiben `hidden` (Adresse oder Ort fehlen; "Ob. Gerberstraße 6" nennt keine Stadt, M2-KONTRAKT 217: nicht nachrecherchiert).
5. Ausgabe als Markdown-Tabelle (Slug, Name, Entscheidung, Quelle, Lat/Lon gerundet) in `docs/C-PINS.md`.

Der Builder liefert Skript, Tests (httpx `MockTransport`, kein Netz) und `docs/C-PINS.md` mit dem **Trockenlauf-Plan**. Den `--live`-Lauf macht Luis (er ruft Nominatim auf: höchstens 15 Anfragen im Abstand von 2 s, rund eine halbe Minute); danach ergänzt der Lauf `docs/C-PINS.md`. Bis dahin sind die Ortspins der Adress- und Zielorte `hidden`, und das erfüllt "bewusst `hidden`" formal; die C3-Abnahme mit Davos, Ischgl, Europapark, Straßburg läuft mit Test-Fixtures (6.1), die echte Probe nach Luis' Lauf.

## 5. Frontend

### 5.1 `app-map` (`shared/ui/map/`, Besitz frontend)

Standalone, OnPush, Signals. Dateien: `map.component.ts/.html/.scss`, `map-loader.service.ts` (2.5), `map-theme.ts` (Tokenfarben aus `getComputedStyle`), `map-layers.ts` (reine Funktionen für Quellen und Layer), `near-me.service.ts` (5.2), `map.models.ts`, je mit Spec.

- **Eingaben**: `mode: 'events' | 'campus' | 'pick'`, `collection` (GeoJSON), `selected` (Slug oder Gebäudenummer), `pin` (nur `pick`), `ariaLabel`, `height`. **Ausgaben**: `featureSelect`, `clusterSelect(slugs[])`, `pinChange({lat, lon})`, `mapError`.
- **Laden**: lazy (Loader), nie im Initial-Bundle. Stile: `style-light.json` oder `style-dark.json` nach `ThemeService.resolved()`. Beim Themewechsel `setStyle`, die Overlays (Quellen, Layer) hängen an `style.load` und werden neu gesetzt.
- **events**: GeoJSON-Quelle `cluster: true`, `clusterRadius: 50`, `clusterMaxZoom: 14`; Layer Cluster (Kreis + Zahl), Einzelpunkt. Klick auf Cluster: Zoom auf `getClusterExpansionZoom`; liegt der Cluster auf `clusterMaxZoom` (gleicher Ort, viele Events), meldet die Karte `clusterSelect` mit den Slugs (`getClusterLeaves`) und die Liste filtert darauf. Klick auf Punkt: `featureSelect(slug)` (Popup mit Titel und Link "Zur Veranstaltung").
- **campus**: GeoJSON-Polygone, `fill-color` als `step` über `count` (vier Stufen aus Token-Farben, Stufe 0 neutral), Umriss, Zähler als `symbol`-Layer (`text-field: ['get','count']`, Schrift aus 2.4). Kein Cluster. Auswahl hebt die Fläche hervor.
- **pick**: ein ziehbarer Marker, Klick setzt ihn, `pinChange` mit 6 Dezimalen; die Zahlenfelder bleiben die Tastaturalternative.
- **A11y**: Container `role="region"` mit `ariaLabel`; MapLibre-Steuerelemente (Zoom, Kompass) sind echte Buttons mit lokalisierten Namen (Option `locale`); Pfeiltasten und `+`/`-` auf der fokussierten Karte (MapLibre-Standard); `prefers-reduced-motion` setzt `animate: false` für `flyTo`/`easeTo`; über der Karte ein Skip-Link "Zur Liste springen"; **Karte ist nie der einzige Zugang** (Liste P11, Tabelle P12). Fehlt WebGL oder scheitert das Laden, setzt die Komponente `data-map-state="error"`, zeigt die Meldung aus P11 und gibt `mapError` aus.
- **Testnaht** statt globaler Objekte: das Host-Element trägt `data-map-state` (`loading|ready|error`), `data-feature-count`, `data-cluster-count`, `data-zoom` und wird bei `idle` aktualisiert.
- **Attribution**: MapLibre `AttributionControl` zeigt den Text aus den Archiv-Metadaten ("© OpenStreetMap"); zusätzlich bei `campus` "© OpenStreetMap-Mitwirkende (ODbL)".

### 5.2 P11 Weltkarte `/karte` (`features/public/pages/map/`)

Route in `public.routes.ts` (lazy, `public.map.title`). Aufbau gemäß PLAN 15.2 und Mock `mock-public.html` (`p11-listd`, `p11-listm`):

- Kopf: `app-segmented` "Gibt es" / "Gab es" (`past=false/true`), Zeitraum (bei "Gab es" Jahresauswahl, bei "Gibt es" ab heute), Kategorie-Chips (`app-filter-select`), Knopf "In meiner Nähe" und der Hinweis "Standort bleibt im Browser und wird nicht gesendet." (Text aus dem Mock).
- Karte (`mode=events`) und **Liste der Treffer** (`app-list-item`, auf dem Handy Sheet von unten, ab `narrow` daneben). Die Liste zeigt dieselben Features wie die Karte; eine Auswahl auf der Karte hebt den Eintrag hervor und umgekehrt. Pin-Klick und Listenzeile führen zu `/e/<slug>`.
- **Daten**: ein Aufruf `GET /api/public/map/events` je Filterstand, **ohne `bbox`** (die Ansicht der Karte, die nach "In meiner Nähe" auf dem Standort liegt, würde sonst in einer URL stehen, E30). Bei `truncated: true` Hinweis "Es werden nur die ersten {n} Orte gezeigt."
- **In meiner Nähe**: Klick löst `navigator.geolocation.getCurrentPosition` aus (nur auf Nutzergeste, `NearMeService`). Position bleibt im Dienst-Signal; die Liste wird nach Haversine-Abstand sortiert und zeigt "{n} km"; die Karte fliegt zur Position und setzt einen eigenen lokalen Punkt (`mode=events` zeichnet ihn als Overlay, nie als Anfrage). Abbruch oder Ablehnung: Meldung "Standort nicht verfügbar. Sortiert wird nach Datum." Es gibt **keinen** Request mit Koordinaten (Test 6.1).
- Zustände: leer "Für diesen Zeitraum gibt es keine Orte mit Koordinaten.", Fehler "Die Karte konnte nicht geladen werden. Die Liste darunter zeigt alle Treffer." (Liste bleibt, wenn nur die Karte scheitert), Laden `app-skeleton`.
- URL-Zustand (`?vergangen=1&k=<slug>`) für teilbare Ansichten.

### 5.3 P12 Campuskarte `/campus` (`features/public/pages/campus/`)

- Zeitraum `app-segmented` "Heute" / "Diese Woche" (Berliner Tage, `from`/`to`), Karte `mode=campus` mit eingefärbten Polygonen und Zähler ("Gebäude 9: 4 Events"), Legende (vier Stufen mit Zahlenbereichen), **Tabelle als Alternative** (`app-table`: Gebäude, Anzahl, Events), Klick auf Fläche oder Tabellenzeile öffnet die Gebäudeliste (Sheet auf dem Handy, Seitenpanel ab `narrow`) aus `GET /api/public/campus/events?building=`. Leer: "Heute ist auf dem Campus nichts geplant." Farben tragen nie allein die Information (Zähler am Polygon plus Tabelle).
- Wird die Zuordnung eines Gebäudes ungenau (`approx`), steht in der Legende "Lage ungefähr".
- Fußzeile mit Attribution.

### 5.4 I23 Orte-Tab (`admin/taxonomy/venues/`)

- Breite und Länge werden freigeschaltet (Zahlenfelder bleiben, Paar-Validierung wie im Backend); neu: "Pin setzen" öffnet ein `app-side-sheet` mit `app-map mode=pick` (Start: vorhandener Pin, sonst Reutlingen), "Adresse suchen" (ruft 4.4, ersetzt nur den Vorschlag im Sheet, Hinweis "Vorschlag von OpenStreetMap. Prüfe den Pin." und die Attribution), Genauigkeit `app-select` (genau / Gebäude / verborgen) mit Hilfetext "Gebäude: auf etwa 100 m genau", Anzeige von Quelle und Zeitpunkt (`geocodeSource`, `geocodedAt`).
- "Adresse suchen" ist für private Orte und Orte ohne Adresse und Stadt deaktiviert, mit den Texten "Private Orte werden nicht extern gesucht." und "Zum Suchen fehlen Adresse und Ort." Fehler: "Adresse nicht gefunden. Setz den Pin von Hand." (found false), "Bitte warte kurz, die Suche läuft höchstens alle 2 Sekunden." (429), "Die Adresssuche ist nicht eingerichtet." (503 `geocode_disabled`).
- `admin.coordinatesLater` und `admin.col.coordinates` ("ab Stufe C") entfallen, die Spec `venues.component.spec.ts` (Spinbuttons disabled) wird umgeschrieben.
- Das Sheet lädt die Karte per `@defer`; ohne WebGL bleibt das Formular voll nutzbar.

### 5.5 Navigation

`PUBLIC_NAV` bekommt `{key: 'map', path: '/karte', icon: 'map', labelKey: 'public.nav.map'}` (Icon-Name im ui-kit prüfen; fehlt `map`, `pin`). Die Handy-Bottom-Bar zeigt Heute, Kalender, Karte, Abos (Suche über die `app-search-pill` im Kopf, PLAN 8.6): neues Feld `phone: false` an `search`; der Desktop-Kopf behält alle fünf. `/campus` ist von `/karte` aus verlinkt (Segment "Welt / Campus" oben) und von P10; kein eigener Platz in der Bar.

### 5.6 B4: PWA öffentlich

**`ngsw-config.json`** (Besitz frontend):

```json
"dataGroups": [
  { "name": "today", "urls": ["/api/public/today"],
    "cacheConfig": { "strategy": "freshness", "timeout": "3s", "maxAge": "1d", "maxSize": 5 } },
  { "name": "events", "urls": ["/api/public/events/*"],
    "cacheConfig": { "strategy": "freshness", "timeout": "3s", "maxAge": "1d", "maxSize": 30 } }
]
```

- `maxAge`: PLAN 9.2 sagt `1d`, der Auftrag nennt 1 h. Gewählt `1d` (Abweichung 7): bei 1 h wäre "Heute" nach einem Abend ohne Netz leer, und genau dafür ist die Gruppe da. Die Veraltung zeigt die Seite selbst: ab einem Stand von mehr als 1 h oder einem anderen Berliner Tag steht "Stand {HH:MM}, möglicherweise veraltet"; am anderen Tag "Stand von gestern". Die Konfiguration ist eine Zeile, falls Luis 1 h will.
- Die Suche (`/api/public/events?q=...`) wird **nicht** zwischengespeichert (Suchtexte gehören nicht in den Gerätecache); `urls` enthält nur den Detailpfad `/events/*` und `/today`. Die Liste für die "nächsten Termine" liefert `/today` (Heute und sieben Tage).
- `/api/public/map/**` und `/api/public/campus/**` stehen in keiner Gruppe (nicht offline, E30-nah: keine Standortableitung im Cache).
- **`navigationUrls`**: `!/e/**` entfällt, damit das zuletzt geöffnete Event offline aus dem App-Shell-Cache gerendert wird (die SPA kennt die Route `e/:slug`; die vom Server gerenderte HTML-Hülle dient Crawlern und Link-Vorschauen, die keinen Service-Worker haben). `!/k/**`, `!/ics/**`, `!/api/**`, `!/.well-known/**`, `!/abo/**`, `!/bestaetigen/**`, `!/tiles/**`, `!/sitemap.xml`, `!/robots.txt` bleiben (Abweichung 8). `ngsw-navigation.spec.ts` trennt künftig "Server-gerendert" (ohne `/e/**`) von "SPA-eigen (`/e/**`)" und prüft beide Listen.
- **Offline-Heute (P01) und P14**: neuer `OnlineService` (`core/browser/online.service.ts`, Signal aus `navigator.onLine` und den Events `online`/`offline`, testbar durch Token). `today.component` zeigt den Hinweis "Offline, Stand {HH:MM}" (Zeit aus `generatedAt`, Berliner Zeit, `formatEventTime`), wenn offline; das Schlagen der Anfrage (Fehler ohne Cache) führt zur Zustandsseite "Du bist offline. Zuletzt geladene Termine siehst du unter Heute." (`OfflinePageComponent`, jetzt real eingebunden als Zustand der Seiten P01/P04 statt toter Route; die Route `/offline` bleibt für den direkten Aufruf).
- **iOS-Installationshinweis** (`layout/install-hint/`, im Rahmen `public`): erscheint nur, wenn (a) iOS Safari (Erkennung `iPhone|iPad|iPod` oder `MacIntel` mit `maxTouchPoints > 1`, ohne Chrome/Firefox-iOS-Kennungen), (b) nicht im Standalone-Modus (`installed-app.token.ts`), (c) noch nie geschlossen. Einmalig: Zustand in `localStorage` (`try/catch`, ohne Speicher erscheint er je Sitzung höchstens einmal über `sessionStorage`-Rückfall, sonst nie). Text: "Zum Installieren: Tippe auf Teilen und dann auf „Zum Home-Bildschirm“." mit Schließen-Knopf. Nicht gleichzeitig mit dem Update-Prompt; kein Cookie.
- **Update-Flow wie Upstream** bleibt (`sw-update.service.ts`, Prompt ohne Schließen-Knopf, Prüfung nach 1 s, alle 5 min, bei Fokus, `activateUpdate()` nur beim Reload). B4 ändert daran nichts; es kommt nur `pwa-update.spec.ts` dazu (6.4).
- Registrierung: `registerWhenStable:30000` heißt bis zu 30 s bis zum Worker, weil der 5-Minuten-Intervall die Zone nie stabil werden lässt (Erwartung, **Annahme**); die E2E-Tests warten deshalb auf `navigator.serviceWorker.controller` mit 45 s Timeout.

### 5.7 EN-Parität

- `Locale = 'de' | 'en'`. Neue Dateien `translations.public.en.ts`, `translations.subscriptions.en.ts`, `translations.shared.en.ts`, `translations.map.de.ts` / `.en.ts`, `translations.shell.en.ts` (nur die Schlüssel des öffentlichen Rahmens). Das EN-Paket wird **lazy** nachgeladen (`import()`), DE bleibt gebündelt; `I18nService.setLocale` lädt, setzt `document.documentElement.lang`, speichert die Wahl in `localStorage` (`try/catch`; reiner Komfort).
- Erkennung beim ersten Besuch: gespeicherte Wahl, sonst `navigator.language` beginnt mit `en`, sonst `de`. `FORMAT_LOCALES = {de: 'de-DE', en: 'en-GB'}`; Zeiten bleiben `Europe/Berlin` (der Text "Berlin time" steht in EN beim Datum der Detailseite); `uiKitIntlFromLang` bekommt `en`.
- **Footer-Umschalter** in `site-footer`: zwei Knöpfe "Deutsch" / "English" (`lang`-Attribute, `aria-pressed`).
- **Parität (Spec reaktiviert)**: `translations.spec.ts` ersetzt `it.todo` durch Tests: (1) jeder Schlüssel aus `publicDe`, `subscriptionsDe`, `sharedDe`, `mapDe` und `PUBLIC_SHELL_KEYS` existiert in `en`; (2) kein EN-Schlüssel ohne DE-Gegenstück; (3) gleiche `{param}`-Platzhalter je Schlüssel; (4) kein leerer String; (5) kein EN-Text identisch zum DE-Text außer einer Allowlist von Eigennamen ("STUPA", "Movienight"); (6) interne Kataloge (admin, dossier, lifecycle, archive, format, events, calendar) bleiben DE-only, `translate` fällt für sie auf DE zurück (Abweichung 9). Das Gendern-Kriterium gilt nur für DE.
- **Server-Hülle** (`/e/<slug>`, Titel, Open Graph, JSON-LD) bleibt Deutsch (kein `hreflang`): sie ist für Crawler, die SPA übersetzt danach. Das steht in `docs/C-ABNAHME.md` als bekannte Grenze.

## 6. Tests und Abnahme

### 6.1 Playwright (Besitz frontend, `e2e/map.spec.ts`, Projekt `map` mit `channel: 'chromium'`)

Das Projekt `map` in `playwright.config.ts` nutzt `channel: 'chromium'` (L20). Die Tests laufen gegen den Produktions-Build hinter nginx (`E2E_BASE_URL=http://127.0.0.1:8081`) mit **Test-Tiles**: eine winzige PMTiles-Fixture (Welt bis Zoom 2 und ein Ausschnitt Reutlingen bis Zoom 12, aus den echten Dateien extrahiert, unter 1 MB, **eingecheckt** unter `frontend/e2e/fixtures/tiles/`), die der Teststack als `tiles_data` mountet. CI lädt nie das Netz.

| # | Test | Prüft |
|---|---|---|
| T1 | Netzwerk-Allowlist | `page.on('request')` über `/karte` und `/campus`: jeder Request hat die Origin der Seite; kein `securitypolicyviolation` (per `addInitScript`-Listener); `data-map-state=ready`; kein `Set-Cookie` |
| T2 | Range-Requests | (nginx, `curl`-Skript `deploy/tiles-range-smoke.sh`) `Range: bytes=0-16383` auf `/tiles/world.pmtiles`: 206, `Content-Range`, `Accept-Ranges: bytes`, `Content-Length: 16384`, kein `Content-Encoding`, starkes ETag, Beginn `PMTiles`; `HEAD` mit voller Länge; `bytes=` über das Ende: 416; Sicherheits-Header genau einmal |
| T3 | Cluster-Rendering | Fixture mit 30 Events an 6 Orten (davon 12 am selben Ort): bei Zoom 5 `data-cluster-count > 0`, Klick auf Cluster erhöht `data-zoom`, Cluster am selben Ort auf Max-Zoom ruft `clusterSelect` und die Liste zeigt nur diese Events |
| T4 | Campuszähler Gebäude 9 | drei veröffentlichte Events heute an Kinosaal 9-133, Maker Space 9-229, FSI 9-U09: `/api/public/campus/buildings` hat `buildingNo 9` mit `count 3`; die Karte zeigt "Gebäude 9: 3 Events", die Tabelle dieselbe Zahl, Klick liefert die drei Titel; ein Event am verborgenen Ort, am privaten Ort und ein abgesagtes zählen nicht |
| T5 | In meiner Nähe | `context.grantPermissions(['geolocation'])`, `setGeolocation({latitude: 48.4829, longitude: 9.1873})`: nach Klick sortiert die Liste nach Abstand; **kein Request** (URL, Query, Header, Body) enthält die Position (Muster `48\.48`, `9\.18`, `lat`, `lon`, `bbox`) und die Karte schickt nach dem Fliegen **keine** neue Anfrage; ohne Erlaubnis erscheint "Standort nicht verfügbar. Sortiert wird nach Datum." |
| T6 | Geolocation per SPA-Navigation | von `/` per Klick auf "Karte" (SPA) und mit aktivem Service-Worker: der Knopf funktioniert (entscheidet die Annahme in 2.6) |
| T7 | Orte-Tab | Pin per Klick in `mode=pick` setzt Zahlenfelder; "Adresse suchen" gegen eine `route`-Attrappe der Admin-API; privater Ort: Knopf deaktiviert, kein Request |
| T8 | axe | `/karte`, `/campus`, Orte-Sheet in Hell und Dunkel, 1280 und 390 × 844: keine `critical`/`serious` |
| T9 | Handy | 390 × 844, kein horizontaler Scroll, Bottom-Bar mit Karte, Liste als Sheet |

### 6.2 Backend (Besitz backend)

- Unit: View-Rundung (Ort mit `lat 48.482617`, `building` ergibt `48.483`; `exact` unverändert; `hidden`, privat, ohne Koordinate ergibt `NULL`); Geocode-Service mit `httpx.MockTransport` (Cache-Treffer ohne Netz, Nichttreffer wird gecacht, Sperre blockiert den zweiten Aufruf innerhalb 2 s, **Redis weg ergibt 503**, Privatort ergibt 422 vor jedem Netzzugriff, falscher Host durch `assert_allowed_url` abgewiesen, `follow_redirects` aus); PATCH-Regeln (`nominatim` nur bei Übereinstimmung mit dem Cache, `coordinates_missing`); Polygon-Schwerpunkt; Hash-Test `campus.geojson`; `PLACE_QUERIES` enthält keinen privaten oder regionalen Ort.
- Integration: Migration `0013_maps` hoch, runter, hoch (Muster `test_migration_0008.py`); `test_db_grants*.py` (`geocode_cache` nur `events_app`, `public_campus_building_v` lesbar für `events_public`, `events_public` kann `campus_building` und `geocode_cache` **nicht** lesen); Kanarienvogel erweitert (privater Ort mit Koordinate, `hidden` mit Koordinate, Entwurf, interne Notiz: nichts davon in `map/events`, `campus/*`); Schemathesis gegen `public-map-v1.json` (Skript `m5_schemathesis.py` um die neuen Routen); Allowlist-Test (neue Modelle und Spalten); `compose-lint`.
- `tests/schema/public-map-v1.json` ist Vertrag; CODEOWNERS deckt `allowlist.py` schon ab, `public-map-v1.json` kommt dazu.

### 6.3 Frontend Jest

`ngsw-navigation.spec` (neu: `/e/**` SPA-eigen, `/tiles/**` ausgeschlossen, keine `dataGroup` trifft `/tiles` oder `/api/public/map`), `ngsw-assets.spec`, `map-layers` (reine Funktionen), `near-me.service` (kein `HttpClient`-Aufruf), `map-loader` (lädt einmal), `check-map-isolation.cjs`, `translations.spec` (5.7), Komponentenspecs für P11, P12, Orte-Sheet, Install-Hinweis, Online-Service.

### 6.4 B4-Tests (Besitz frontend)

- `e2e/offline.spec.ts` (Projekt `chromium`, Produktions-Build): `/` online laden, auf `navigator.serviceWorker.controller` warten (Neuladen; bis 45 s), `context.setOffline(true)`, `/` neu laden: Liste und "Offline, Stand HH:MM"; zuletzt geöffnetes `/e/<slug>` offline lesbar; ein nie geöffnetes Event zeigt den Offline-Zustand.
- `e2e/pwa-update.spec.ts`: Teststack `frontend/scripts/pwa-update-stack.sh` startet einen Wegwerf-nginx mit der Produktions-`nginx.conf` und einer **beschreibbaren Kopie** von `dist` (Vorbild `docs/B1-ABNAHME.md`, Abschnitt "Wegwerf-Container vor der Host-API"). Ablauf: laden, Worker aktiv; Kopie ändern (ein Byte in `index.html` und neuer SHA-1 im `hashTable` von `ngsw.json`, dort `timestamp` erhöhen: **Annahme** über das Hash-Format, der Builder prüft es an einer echten `ngsw.json`); innerhalb der Prüfintervalle erscheint der Prompt "Neue Version verfügbar. [Neu laden]" ohne Schließen-Knopf; Klick lädt neu; die neue Version läuft. Parallel Jest für den Dienst (existiert).
- `e2e/en.spec.ts`: Footer-Umschalter, `lang="en"`, Heute/Suche/Kalender/Get started/Abos ohne deutsche Reste (Stichprobe auf Schlüssel), Datum im EN-Format, Wahl überlebt Neuladen, axe in EN.

### 6.5 Abnahme (wörtlich aus PLAN 16.2 und 16.3, jeweils mit Beleg in `docs/C-ABNAHME.md`)

- **C1** Karte lädt ohne einen Request an Dritte (Netzwerk-Test, T1), Range-Requests hinter nginx funktionieren (T2).
- **C2** alle öffentlichen Orte haben Koordinaten oder sind bewusst `hidden`; private Orte nie extern geocodiert; kein Autocomplete (Belege: `docs/C-PINS.md`, Unit-Tests 6.2, `grep` auf clientseitige Nominatim-Aufrufe im Frontend ist leer, Trockenlauf-Plan, nach Luis' `--live`-Lauf die Tabelle).
- **C3** Davos, Ischgl, Europapark, Straßburg erscheinen; Liste liefert dieselben Treffer; kein Request enthält Koordinaten (T3, T5, mit Fixtures; echte Probe nach dem Pin-Lauf).
- **C4** Gebäude 9 (Kinosaal 9-133, Maker Space 9-229, FSI 9-U09) zählt korrekt; keine OSM-Abhängigkeit zur Laufzeit (T4; Belegt durch T1 und `grep overpass` im Backend außerhalb des Skripts leer).
- **B4** "Heute" offline lesbar (`offline.spec`); EN-Paritäts-Spec grün (`translations.spec`); Update-Prompt-E2E grün (`pwa-update.spec`).
- Gates wie bisher: `ruff`, `ruff format --check`, `basedpyright` (auf NixOS aus der venv nicht startbar, B3-ABNAHME: dieselbe Version aus nix), `pytest` Unit und Integration, `npm run lint`, `typecheck`, `jest`, `build` (Initial-Gesamtgröße **nicht** über dem B3-Stand, B1-ABNAHME 641 kB), `compose-lint.sh`, `smoke.sh`, `public-smoke.sh`, `m5b_acceptance` und die B3-Abnahme unverändert grün.
- NixOS-Fallen (aus `docs/M*-ABNAHME.md`): Backend-Units mit `LD_LIBRARY_PATH` (libstdc++, libmagic) wie in `deploy/dev-up.sh`; Playwright-Browser aus `nix build nixpkgs#playwright-driver.browsers` mit `PLAYWRIGHT_BROWSERS_PATH`, `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true`; `pmtiles` aus nixpkgs; nginx-Prüfungen im Wegwerf-Container wie `docs/B1-ABNAHME.md`; Units `stupa-api`, `stupa-worker`, `stupa-ng`; `basedpyright` nicht aus der venv.

## 7. Abweichungen vom PLAN und vom Auftrag

1. **`public_precision`**: `exact|building|hidden` bleibt (PLAN und Auftrag sagen `area`). Umbenennen würde Migration 0003, CHECKs, Admin-API, Labels und Specs berühren, ohne Nutzen. `building` ist auf 3 Dezimalen gerundet.
2. **`maplibre-gl-csp` gibt es nicht** (E404); `maplibre-gl@6.13.0` ist ESM mit separater Worker-Datei, die same-origin ohne `blob:` läuft. Der PLAN-Satz "CSP-Build" wird zu "Worker same-origin über `setWorkerUrl`".
3. **Keine Spalte `campus_building.venue_ids`** und `venue.campus_building_no` bleibt ungenutzt: die Zuordnung läuft über `venue.building_no` (im Seed aus dem Namen abgeleitet), damit sie nur an einer Stelle steht. `seed/campus.geojson` liegt unter `backend/seeds/campus.geojson`, wo die anderen Seeds liegen.
4. **CSP und Permissions-Policy**: `worker-src` bleibt `'self'` (kein `blob:`); `geolocation=(self)` gilt **global**, nicht nur auf Kartenrouten, weil Richtlinien je Dokument gelten und der Service-Worker das gecachte `index.html` samt Headern liefert (Annahme, T6 entscheidet; Plan B in 2.6). Der Auftrag wollte `blob:` und eine Location-Lösung.
5. **MapLibre als Asset unter `/map/`** statt als Angular-Chunk, damit der Precache (`app`-Gruppe mit `/*.js`) ihn nicht für jeden Erstbesucher lädt (L16). Rückfall: normaler Chunk.
6. **Feed und ICS bleiben ohne Koordinate** (PLAN 8.2 und 8.3 nennen `venue.lat/lon` und `GEO`). Das wäre eine zusätzliche Allowlist-Entscheidung außerhalb von C1 bis C4; Vorschlag in 9.
7. **`maxAge` der `dataGroup`**: `1d` (PLAN 9.2) statt 1 h (Auftrag); zwei Gruppen `today` und `events` statt einer; Suche nicht gecacht.
8. **`navigationUrls`**: `/e/**` wird für den Offline-Shell freigegeben (der Auftrag sagt "inkl. /e/**", PLAN 9.1 schließt es aus); `/k/**` bleibt ausgeschlossen.
9. **EN-Parität** gilt für alle öffentlichen und gemeinsamen Schlüssel (rund 260 plus Karte), nicht für die internen Kataloge (admin, dossier, lifecycle, archive, format, events, calendar, zusammen rund 920 Schlüssel); die Kataloge bleiben TS-Dateien statt `en.json`.
10. **Migration `0013_maps`** statt "0010"; **Version `maplibre-gl@6.13.0`** statt der neuesten (6.15.0), weil nur sie die Zwei-Wochen-Grenze mit Abstand erfüllt.
11. **Live-Läufe**: Overpass einmal durch den Builder (4.6), Nominatim `--live` nur durch Luis (4.7); die Probe der Pins in `docs/C-PINS.md` entsteht erst dann.

## 8. Verzeichnisbesitz und Reihenfolge

| Besitzer | Dateien |
|---|---|
| **tiles-builder** | `scripts/build-tiles.sh`, `scripts/gen-map-style.mjs`, `deploy/tiles.lock`, `deploy/tiles-range-smoke.sh`, `deploy/**` (`web/nginx.conf`, `web/security-headers.conf`, `web/Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `compose-lint.sh`, `smoke.sh`, `dev-up.sh`, `backup.sh` falls W-C3 bejaht), `.gitignore` (`deploy/tiles/`), `frontend/public/map-style/**` (Style, Glyphen, Sprites, `PROVENANCE.map-assets.json`), `docs/TILES.md`. **Ausnahme, Commit 1 vor allem anderen:** legt `feat/c-karten` an und trägt in `frontend/package.json` und `package-lock.json` genau `maplibre-gl@6.13.0`, `pmtiles@4.5.0` und `@protomaps/basemaps@5.7.2` (dev) ein ("build(deps): map libraries") |
| **backend** | `backend/**` (Migration `0013_maps`, `taxonomy/campus.py`, `publicapi/map_router.py`, `publicapi/query/*`, `admin/venues_router.py`, `geocode/`, Settings, Tests), `backend/seeds/campus.geojson`, `backend/scripts/pin_venues.py`, `backend/tests/schema/public-map-v1.json`, `.github/CODEOWNERS` (Zeile für das Schema), `docs/C-CAMPUS-OSM.md`, `docs/C-PINS.md` |
| **frontend** | `frontend/**` außer `frontend/public/map-style/**` und den drei Abhängigkeitszeilen aus Commit 1 (also `angular.json` Asset-Kopie nach `/map/`, `proxy.conf.json`, `ngsw-config.json`, `shared/ui/map/`, `features/public/pages/map|campus`, Orte-Tab, Nav, Install-Hinweis, `OnlineService`, i18n, `e2e/**`, `playwright.config.ts`, `scripts/check-map-isolation.cjs`, `scripts/pwa-update-stack.sh`) |
| **zuletzt fertig** (frontend) | `docs/C-ABNAHME.md` mit den Belegen aus 6.5 |

Commit-Vorschlag: tiles T1 (deps), T2 (`build-tiles.sh`, `tiles.lock`, `.gitignore`, `docs/TILES.md`), T3 (Style, Glyphen, Sprites), T4 (nginx, Compose, Dev, smoke, lint); backend B1 (Migration, Modelle, View, Allowlist, Tests), B2 (Karten- und Campusrouten, Schema), B3 (Geocoding, Admin, Settings), B4 (Overpass-Schritt, Seed, `pin_venues.py`, Docs); frontend F1 (Loader, `app-map`), F2 (P11), F3 (P12), F4 (I23), F5 (Nav), F6 (PWA: ngsw, Online, Install-Hinweis, E2E), F7 (EN), F8 (`C-ABNAHME.md`).

## 9. Offene Weichen für Luis

| # | Frage | Vorschlag |
|---|---|---|
| W-C1 | Dürfen Orte ohne Adresse (Davos, Ischgl, Europapark, Straßburg, Montafon, Flumserberg, Serfaus-Fiss-Ladis) per Ortsname geocodiert werden? Ohne das fehlt C3 "Davos, Ischgl, Europapark, Straßburg erscheinen" | Ja, kuratierte Liste `PLACE_QUERIES` (4.7), Präzision `building`; alle anderen `hidden` |
| W-C2 | Reicht Weltkarte bis Zoom 5 (15 MB)? Alpen und Süddeutschland würden unscharf | Später optional ein drittes Band SW-Deutschland und Alpen bis Zoom 10 (41 MB gemessen), Mehraufwand Style und Layer |
| W-C3 | Kachel-Dateien in `backup.sh` aufnehmen (32,5 MB), weil der gepinnte Build nach einer Woche verschwindet? | Ja |
| W-C4 | Handpolygone für Gebäude, die OSM nicht hergibt: Luis liefert Koordinaten oder die Gebäude bleiben ungezeichnet | ungezeichnet lassen, Tabelle in `docs/C-CAMPUS-OSM.md` |
| W-C5 | Mini-Karte auf P04 und `GEO`/Koordinate im Feed und ICS (PLAN 8.2, 8.3, 15.2) | eigener kleiner Schritt C5 nach der Abnahme, mit Allowlist-Review |
| W-C6 | Nominatim-Lauf für die Bestandsorte | Luis führt `pin_venues.py --live` einmal aus (höchstens 15 Anfragen) |
| W-C7 | ODbL-Share-Alike für die abgeleiteten Campus-Polygone | rechtlich nicht geprüft (wie in `extern.md` 2.5); Hinweis in der Attribution, Klärung mit der Datenschutzbeauftragten oder der Hochschule |
| W-C8 | `Permissions-Policy: geolocation=(self)` gilt global statt nur auf `/karte` und `/campus` (PLAN 11.2, E30; Abweichung 4, T6 belegt den Grund: SPA-Navigation und Service-Worker behalten die Richtlinie des ersten Dokuments). Jede Seite der eigenen Origin dürfte die Standortabfrage stellen, es gibt aber nur einen Aufrufer (`NearMeService`), `connect-src 'self'` verhindert Abfluss, und ein Bundle-Test (`check:map`) lässt `geolocation` nur in dieser Datei zu | Global lassen und PLAN 11.2/E30 anpassen; Alternative: Karten-Links als Voll-Navigation (`ngsw-bypass`) und die Richtlinie nur dort, Preis: kein SPA-Wechsel zur Karte |
