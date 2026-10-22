# B1/B2-Kontrakt: Die öffentliche Seite

Stand 2026-10-22, gelesen auf `feat/m5b-vereinfachung` (HEAD `e43a482`, M1 bis M5b committed); der Branch `feat/b1-public` entsteht im Integrationsschritt. Verbindlich: `stupa-events-plan/ENTSCHEIDUNGEN.md` (inkl. Kurskorrektur 21.10.: drei Zustände, Bild optional, öffentlich nur `published` und `archived` mit Slug), `PLAN.md` §8.1 bis 8.6, §9.1 und 9.2 (nur vorbereiten), §11.2, §11.7, §15.2 (P01 bis P05, P07, P10, P13, P14), §16.2 B1/B2, §18 Minor 2 und 3. Alles aus `M1` bis `M5B-KONTRAKT.md` gilt weiter, soweit unten nichts anderes steht. "Nur Belegtes": was ich gelesen habe, steht mit Datei; was ich nicht gelesen oder nicht gemessen habe, steht als "Annahme" oder "Builder prüft".

Regeln wie bisher: Upstream-Konventionen, camelCase mit `extra=forbid`, Problem+JSON, tz-aware, öffentliche Router nur über `events_public`, kein `Set-Cookie` auf öffentlichen Routen, Angular standalone mit signals und ui-kit @ `8ad3782`, i18n de, Jest, Playwright, `PROVENANCE.json`, kleine Dateien mit Kopf-Docstring, keine Trennkommentare. Code und Commits Englisch, UI Deutsch gegendert. Kein Eingriff in Live-Systeme (nur lokales Docker und die Dev-Dienste). **Löschen statt Verstecken** gilt auch hier: die Platzhalter-Startseite `pages/home` und der `homeRedirectGuard` samt Spec fallen weg (3.1).

## 0. Umfang

**Drin (B1 und der Teil von B2, den der Auftrag nennt):** Public-Shell, Heute (P01, mit "Heute am Campus" aus P10), Suche mit Facetten (P02), Kalender (P03), Event-Detail (P04), Kategorie (P05), Abos nur mit ICS je Kategorie und `all` (P07), Rückblick (P13), Fehler/Offline/Rechtliches (P14), Einzel-ICS, HTML-Hülle mit Open Graph und JSON-LD, Sitemap, robots, Cache, Rate-Limit, nginx-Log ohne Query, Handy-UX.

**Nicht drin:** Profil-ICS, Token-Verwaltung und alles mit `subscriber` (B3; PLAN §16.2 führt Profil-ICS unter B2, der Auftrag zieht es nach B3, siehe 8.1), Get started P06, P08, P09, Dauerangebote und Öffnungszeiten (M7, darum zeigt P10 nur die heutigen Events), Karten P11/P12 (Stufe C), PWA-`dataGroup` und EN-Parität (B4), Impressums- und Datenschutztexte (B5; hier Platzhalterseiten), Mail-Abo (Platzhalter "kommt bald").

## 1. Lückenanalyse (Ist am Arbeitsbaum, Soll aus PLAN)

| # | Soll | Ist (Beleg) | Lücke und Maßnahme |
|---|---|---|---|
| L1 | Liste/Suche mit Facetten für Anonyme | nur `GET /api/public/feed/events` (Filter `from,to,since,category,organization`, Cursor auf `(starts_at,id)`), `publicapi/router.py`, `service.py`; interne Suche ist an Reader und Rechte gebunden (`search/filters.py`) | neuer Dienst `publicapi/query/` auf `public_event_v`, 2.2 bis 2.4 |
| L2 | Volltext auf der View | `event.search_tsv` (generiert aus Titel A, Summary B, Beschreibung C, `events/models.py`) und Trigram-Index `ix_event_title_trgm` existieren (`0006`), die View `public_event_v` führt `search_tsv` **nicht** (Spaltenliste in `allowlist.py`), `events_public` sieht keine Tabelle | Migration `0008`: View um `search_tsv` erweitern (Abschnitt 2.1) |
| L3 | Detail mit mehreren Bildvarianten | `PublicImage` trägt nur `card_1200` (`service._image`, `CARD_VARIANT`) | neues Modell `PublicImageSet` (thumb, card, og) für die neuen Routen; Feed-Schema 2 bleibt unverändert (`tests/schema/feed-v2.json`) |
| L4 | Kategorie-Seite mit Beschreibung, Zählern | `public_category_v` hat nur `slug,name,kind,parent_slug` (`PUBLIC_CATEGORY_COLUMNS`); `category` hat keine Beschreibung, keine `sort`/`active` in der View (`taxonomy/models.py`) | Migration `0008`: `category.description`, View um `description,sort,active` |
| L5 | Kategorien-Facette über alle Kategorien eines Events | die View führt nur `primary_category_id` und dessen Elternkategorie (`0007` `_VIEW_BODY`) | Facette zählt Hauptkategorie und Elternkategorie (wie `_categories()` und der ICS-Filter); Mehrfachkategorien gibt es im Modell nicht, kein Aufwand hier |
| L6 | HTML-Hülle | keine Route; nginx leitet `/e/`, `/k/`, `/suche`, `/sitemap.xml`, `/robots.txt` schon an die API (`deploy/web/nginx.conf`), die API kennt die Pfade nicht; `= /` und `/kalender`, `/rueckblick` fehlen; kein gebautes `index.html` im API-Image (`backend/Dockerfile` kopiert nur `app worker migrations seeds`) | Abschnitt 2.8 und 5.1 |
| L7 | Cookie-freie Hülle | `CsrfMiddleware` setzt das XSRF-Cookie auf jeder Antwort ohne Cookie, außer unter `PUBLIC_PREFIXES = ("/api/public/", "/ics/")` (`shared/errors.py`, `middleware.py`); `/e/…`, `/` wären also nicht ausgenommen, und `GET /api/auth/me` (die SPA ruft es bei jedem Start, `app.config.ts`) setzt das Cookie für jeden anonymen Besucher | Abschnitt 2.9: Cookie nur noch, wenn die Anfrage ein Session-Cookie trägt; Hülle-Pfade zählen als öffentlich |
| L8 | `X-Robots-Tag: noindex` nur für JSON | `SecurityHeadersMiddleware` setzt es für alles unter `PUBLIC_PREFIXES` | die Hülle liegt außerhalb dieser Präfixe, bleibt also indexierbar (gewollt); Test sichert beides |
| L9 | Einzel-ICS | `ics_router.py` kennt `all.ics` und `k/<slug>.ics`; PLAN §8.3 nennt `/ics/c/<slug>.ics`, gebaut ist `/ics/k/` | `GET /ics/e/{slug}.ics` neu (2.7); der Pfadunterschied `c`/`k` bleibt (8.3) |
| L10 | Sitemap, robots | keine Route; Worker `rebuild_public_cache` baut Feed und ICS (`worker/public_cache.py`) | Sitemap als weiterer Snapshot, robots statisch (2.8) |
| L11 | Antwort-Cache und Rate-Limit für öffentliche GETs | Feed/ICS aus Worker-Snapshot (`publicapi/cache.py`, `serving.py`), sonst live; Redis-Rate-Limiter existiert (`shared/ratelimit.py`, `antiabuse.get_rate_limiter`, fail-open), `rate_limit_search` gilt nur intern; nginx hat `limit_req ev_public 10r/s burst 20` (`nginx.conf`), kein `proxy_cache` | Abschnitt 2.10 und 5 |
| L12 | Log ohne Query | `ev_noquery` hängt nur an `/api/public/` und `/ics/`; der Server-Standard-Log (Format `combined`) steht auf allen anderen Locations und schreibt `$request` samt Query, also `/suche?q=…` | Server-Block bekommt `access_log … ev_noquery` als Standard (5.1) |
| L13 | Pool-Größe der Public-Rolle | `events_public` hat `CONNECTION LIMIT 8` (`deploy/db/roles.sql`), die Engine `pool_size=5, max_overflow=5` (`publicapi/db.py`): ein Prozess kann das Limit allein überschreiten, API und Worker teilen die Rolle | `pool_size=4, max_overflow=2`; Facetten und Treffer laufen nacheinander auf einer Sitzung, nie parallel (Builder prüft das Worker-Limit) |
| L14 | Public-Frame im SPA | `ShellFrame` `public` gilt nur ohne Session (`shell.component.ts`); `/` ist eine Platzhalterseite mit Anmelden-Knopf und `homeRedirectGuard` schickt Angemeldete nach `/dossiers`; Header hat nur Marke, Theme-Schalter, Anmelden; Footer nur `footer.coBranding`; es gibt keine öffentliche Bottom-Bar | Abschnitt 3 |
| L15 | `formatEventTime` für Berliner Zeit | liegt unter `features/dossiers/api/event-time.ts` (benutzt von `archive-event.component.ts`) | nach `shared/event-time.ts` verschieben, Imports nachziehen (löschen statt Verstecken) |
| L16 | Service-Worker-Ausschlüsse | `ngsw-config.json` schließt `/api/**, /.well-known/**, /ics/**, /e/**, /k/**, /tiles/**, /sitemap.xml` aus, `/robots.txt` fehlt; `core/pwa/ngsw-navigation.spec.ts` prüft die Liste | `!/robots.txt` ergänzen; `/`, `/suche`, `/kalender`, `/rueckblick` bleiben beim SW (App-Shell, offline-fähig für B4); Spec nachziehen. Das ist PLAN §18 Minor 9 (Reload auf `/e/…` fällt auf die Hülle zurück, nur SPA-interne Navigation geht offline) |
| L17 | Blockierendes `theme-init.js` gegen den Hell-Blitz (PLAN 8.6) | `index.html` setzt `data-theme="light"` fest; `ThemeService.init()` läuft erst im App-Initializer; kein `/theme-init.js` | Datei `frontend/public/theme-init.js` (same-origin, kein Inline-Skript), im `<head>` vor den Bundles; liest `localStorage['ev.theme']` (Schlüssel `STORAGE_KEY` im ThemeService), fällt auf `prefers-color-scheme` zurück |
| L18 | Standard-OG-Bild für Seiten ohne Poster | keines; WhatsApp und Signal lesen kein SVG | `frontend/public/og-default.png`, 1200x630, aus dem Kit-Wortmarken-Logo (Builder erzeugt; kein Fremdmaterial) |
| L19 | Public-E2E | `frontend/e2e/` hat `m1` bis `m5b`, kein Public-Spec, keinen Netzwerk-Allowlist-Test | `public.spec.ts`, 6.2 |
| L20 | Antwortzeit-Nachweis | `m5_search.py` misst intern; kein Public-Perf-Test | 6.1, Skript `scripts/b1_perf.py` |

## 2. Backend: Public-API-Erweiterungen

Alle neuen Routen: `GET` und `HEAD`, Router im Modul `publicapi`, ausschließlich `get_public_session` (Rolle `events_public`), keine Session-Auflösung, kein Cookie, CORS aus. Antwortmodelle `CamelModel` mit `extra=forbid`, gebaut feldweise aus View-Zeilen (kein ORM-`model_dump`; der Lint-Test `test_public_module_builds_responses_field_by_field` deckt neue Dateien im Modul mit ab). Fehler: Problem+JSON. **Nie PII:** keine E-Mail-Adressen, keine Personen, keine Kontaktdaten, keine internen Zustände, Kommentare, Anhänge, nur Allowlist-Felder. Die Pfade unter `/api/public/` tragen `X-Robots-Tag: noindex` wie bisher.

Neue Dateien (alle < 200 Zeilen, je Kopf-Docstring):

```
backend/app/modules/publicapi/
  site_schemas.py      Pydantic-Modelle der neuen Routen (2.2 bis 2.6)
  site_router.py       /events, /events/{slug}, /today, /categories, /calendar, /archive
  query/__init__.py
  query/filters.py     Bedingungen aus Parametern (Zeit, Kategorie, Organisation, Suche)
  query/search.py      Wortsuche über search_tsv und Trigram (wiederverwendet search.words/clauses)
  query/facets.py      Facetten (disjunktiv), Monats- und Tageszählung
  query/cards.py       Zeile -> PublicEventCard / PublicEventDetail / PublicCalendarEntry
  respcache.py         Antwort-Cache in Redis, ETag/304
  ratelimit.py         Abhängigkeiten public_limit / search_limit
  clock.py             Abhängigkeit now() (testbar), Berliner Tagesgrenzen
  shell/__init__.py
  shell/router.py      /, /suche, /kalender, /rueckblick, /e/{slug}, /k/{slug}, /sitemap.xml, /robots.txt
  shell/page.py        index.html laden, Kopf einsetzen
  shell/meta.py        Titel, Beschreibung, OG-Tags je Seite
  shell/jsonld.py      schema.org/Event
  shell/sitemap.py     Sitemap-Bytes (Worker und Live)
```

### 2.1 Migration `0008_public_site` (`down_revision = "0007_event_dossier"`)

Muster `0006`/`0007` (additiv, `downgrade()` stellt den Zustand der View und löscht die Spalte):

1. `ALTER TABLE category ADD COLUMN description text` mit `CHECK (description IS NULL OR char_length(description) <= 300)` und der Steuerzeichen-Regel von `CONTROL_CHARS`.
2. `CREATE OR REPLACE VIEW public_event_v` mit **unverändertem Rumpf** (`_VIEW_BODY` aus `0007`) und einer neuen Spalte **am Ende**: `e.search_tsv` (Postgres erlaubt bei `CREATE OR REPLACE VIEW` nur angehängte Spalten, darum steht sie hinter `description_md`). `search_tsv` ist aus `title`, `summary`, `description_md` generiert; alle drei sind öffentliche Felder der View. Nichts Internes fließt hinein (`EVENT_SEARCH_TSV`, `events/models.py`).
3. `public_category_v` neu: `slug, name, kind, parent_slug` unverändert vorn, dazu `description, sort, active` am Ende. Der `GRANT SELECT … TO events_public` bleibt (bei `CREATE OR REPLACE` erhalten; der Test `test_view.py` prüft die Rechte nach der Migration).
4. Kein neuer Index nötig: die View ist eine einfache Inline-View, der Planer schiebt `search_tsv @@ …` und `immutable_unaccent(title) …` auf `event` hinunter, wo `ix_event_search_tsv` und `ix_event_title_trgm` liegen (Annahme; **Builder belegt es mit `EXPLAIN` im Perf-Test** 6.1; bei Seq-Scan kommt ein Teilindex `WHERE state IN ('published','archived')` dazu).
5. `allowlist.py` (CODEOWNERS-geschützt): `PUBLIC_VIEW_COLUMNS` + `search_tsv`; `PUBLIC_CATEGORY_COLUMNS` + `description, sort, active`; `PUBLIC_FIELDS` + die neuen Modelle (2.2 bis 2.6): `PublicOrganizationRef, PublicImageSet, PublicImageVariant, PublicEventCard, PublicEventDetail, PublicCalendarEntry, PublicCalendarDay, PublicCalendarOut, PublicTodayDay, PublicTodayOut, PublicSearchOut, PublicFacetCategory, PublicFacetOrganization, PublicFacetMonth, PublicFacets, PublicCategoryOut, PublicArchiveOut`. Der bestehende Allowlist-Test (Modell-Felder gegen `PUBLIC_FIELDS`, View-Spalten gegen `PUBLIC_VIEW_COLUMNS`) bleibt der Wächter; jedes neue Feld fehlt dort, bis es eingetragen ist.
6. Seeds (`taxonomy/reference.py`, Builder prüft den Ort): Beschreibungen der Referenzkategorien aus der Karte (`stupa-wp-plugin-phase1/KARTE.md` §2.3 nennt Slugs und Namen, keine Beschreibungen; die Sätze aus `mock-public.html` P07 sind Vorlage: "Movienight und Filmabende", "Partys und Tanzabende", "Kneipentouren, Karaoke, Stammtische", "Löten, Reparieren, Ausprobieren", "Sitzungen, Game Together, LAN", "Live-Musik"). Das Admin-Formular I23 und die Update-Route der Kategorie bekommen das Feld `description` (Recht `taxonomy.manage`, Builder prüft die Route).

### 2.2 `GET /api/public/events`: Liste und Suche mit Facetten

Parameter (alle optional; unbekannte Parameter werden ignoriert wie beim Feed, `extra` gilt nur für Körper):

| Name | Typ | Regel |
|---|---|---|
| `q` | string, <= 100 | Suchtext, Parser `search.words.parse` (zwei Zeichen Minimum, acht Wörter, `invalid_query`/`query_too_long` als 422, wie intern) |
| `category` | slug, wiederholbar, <= 10 | Treffer, wenn `category_slug` oder `category_parent_slug` passt (ODER-verknüpft) |
| `organization` | slug, wiederholbar, <= 10 | `organization_slug` (ODER) |
| `from`, `to` | Datum `YYYY-MM-DD` | Berliner Kalendertage, `from` inklusive ab 00:00, `to` inklusive bis 23:59:59; Bedingung `ends_at >= from_start AND starts_at <= to_end` (mehrtägige Events zählen mit). `to < from` ist 422 |
| `past` | `0`/`1`, Standard `0` | `0`: nur Events mit `ends_at >= jetzt`, wenn weder `from` noch `to` gegeben sind; `1`: nur `ends_at < jetzt`, absteigend sortiert. Mit `from`/`to` gilt `past` nicht |
| `limit` | 1 bis 50, Standard 20 | |
| `cursor` | opak | 2.2.3 |

Berliner Tagesgrenzen kommen aus `clock.py` (`ZoneInfo("Europe/Berlin")`), nie aus der Server-Zeitzone. `now` ist die Abhängigkeit `clock.now`, in Tests ersetzbar.

**Antwort** `PublicSearchOut`: `{items: PublicEventCard[], nextCursor: string|null, total: int|null, facets: PublicFacets|null}`. `total` und `facets` stehen nur auf der ersten Seite (ohne `cursor`), sonst `null`.

`PublicEventCard`: `slug, title, summary, startsAt, endsAt (UTC), allDay, startsOn, endsOn, tzid, status (scheduled|cancelled|postponed), statusReason {code,text}|null, organization {slug,name,short}, venueName, categories [{slug,name,kind}], image {url,width,height,alt}|null (Variante thumb_400), path ("/e/<slug>")`. Alle URLs sind **wurzelrelativ** (`/api/public/media/<id>.webp`, `/e/<slug>`), nie absolut: in der Entwicklung liegt `public_base_url` auf :8081 und die SPA auf :4200, ein absolutes Bild wäre fremde Origin und fiele durch den Netzwerk-Test (6.2). Der Feed behält absolute URLs.

`PublicOrganizationRef {slug,name,short}` ohne `id` (der Feed trägt die `id`; hier nicht nötig).

**2.2.1 Suche.** Mit `q` dieselbe Logik wie intern, aber nur ihre reinen Bausteine: `search.words.parse`, `search.clauses.word_sql/word_match/trigram_match/trigram_rank` (String-Bausteine mit gebundenen Parametern, keine Datenbankzugriffe; der Import von `search.filters.Reader` in `clauses.py` ist nur ein Typimport). Sichtbarkeit und Rechte der internen Suche werden **nicht** importiert; die View ist die Sichtbarkeitsgrenze. Ein Wort trifft, wenn `search_tsv @@ tsquery(de_unaccent)` oder (Wort >= 3 Zeichen) die Trigram-Ähnlichkeit zum entakzentuierten Titel greift (Schwellen 0,5/0,6 aus `clauses.py`); alle Wörter müssen zutreffen. Rang: `ts_rank_cd(search_tsv, …)` plus Titel-Bonus plus Trigram-Rang (`TITLE_BONUS`, `TRIGRAM_FACTOR`). `statement_timeout` ist 2 s per Rolle (`deploy/db/roles.sql`); ein Timeout wird zu 503 `search_unavailable`, nicht zu 500.

**2.2.2 Sortierung.** Ohne `q`: `starts_at, id` aufsteigend (`past=1`: absteigend). Mit `q`: Rang absteigend, dann `starts_at, id`.

**2.2.3 Cursor.** Ohne `q`: der bestehende Keyset-Cursor `cursor.encode(starts_at, id)`, bei `past=1` mit umgekehrtem Vergleich. Mit `q`: ein eigener Cursor `{"o": <offset>}`, höchstens Offset 200 (Suchtreffer jenseits davon liefern `nextCursor: null`); ein Rang ist ein Gleitkommawert und taugt nicht als Keyset-Schlüssel. Beide Formen sind `base64url`-JSON; ein Cursor der falschen Form ist 422 `invalid_cursor`.

**2.2.4 Facetten** (`PublicFacets`): `categories [{slug,name,count}]` (Hauptkategorie und Elternkategorie je Event, Eltern zählen die Kinder mit), `organizations [{slug,name,short,count}]`, `months [{month:"YYYY-MM",count}]` (Berliner Monat des Beginns). **Disjunktiv:** jede Facette wird über alle Filter außer ihrem eigenen berechnet, damit ein gewählter Chip die Geschwister weiter mit Zahlen zeigt. Alle Facetten und `total` laufen nacheinander auf derselben Sitzung (L13), je `GROUP BY` über denselben Basisfilter. Höchstens 30 Kategorien, 30 Organisationen, 12 Monate; Sortierung `count desc, name`. Facetten mit Zähler 0 entfallen, ausgenommen gewählte Werte.

**2.2.5 Zeit-Chips** ("heute, Wochenende, 7 Tage, Monat" aus P02) sind reine Client-Sache: der Client rechnet `from`/`to` in Berliner Tagen. Der Server kennt nur Daten. Die URL der SPA trägt dieselben Parameter (teilbar).

### 2.3 `GET /api/public/events/{slug}`: Detail

Pfadparameter `slug` mit Muster `^[a-z0-9][a-z0-9-]{0,79}$` (Slugs sind `<Datum>-<Titel bis 60>` plus Suffix, `events/slugs.py`); ein anderes Muster ist 404, kein 422 (kein Orakel). Unbekannt oder nicht öffentlich: 404 `not_found`. **Kein 410**: `events_public` sieht nur die View; ein zurückgezogenes Event ist dort schlicht weg und von einem nie dagewesenen nicht zu unterscheiden, und eine Unterscheidung würde Entwürfe verraten (8.2).

`PublicEventDetail` = `PublicEventCard` (Bildvariante hier `PublicImageSet`) plus: `descriptionHtml` (`textsafe.text_html`, nh3-Allowlist `p a strong em ul ol li br`, Links `rel="noopener noreferrer nofollow"`), `venue {name,address,city}|null`, `venueText`, `ticketUrl`, `websiteUrl`, `costText`, `format {slug,title}|null`, `icsUrl` ("/ics/e/<slug>.ics"), `isPast` (bool, `ends_at < now`), `updatedAt`, `sequence`, `more` (bis zu 4 kommende Events desselben Formats ohne dieses, als `PublicEventCard[]`; leer ohne Format).

`PublicImageSet {thumb, card, og: {url,width,height}, alt, credit}` aus `hero_derivatives` (`thumb_400`, `card_1200`, `og_1200x630`; die Spalte enthält laut `attachment_poster_ok` alle drei), `null` ohne Poster. Die Mitveranstalter-Frage (PLAN §18 Minor 3, "D12") bleibt offen: es steht nur die Hauptorganisation drin.

### 2.4 `GET /api/public/today`

Parameter keine. Antwort `PublicTodayOut`: `{generatedAt, date: "YYYY-MM-DD" (Berliner Heute), today: PublicEventCard[], days: [{date, items: PublicEventCard[]}]}`. `today` enthält jedes Event, das heute (Berliner Tag) läuft oder beginnt und noch nicht beendet ist, plus heutige, bereits beendete bleiben **drin** (die Liste zeigt "Heute am Campus" für den ganzen Tag), sortiert nach Beginn. `days` sind die nächsten 7 Tage nach heute (nur Tage mit Events), Zuordnung nach Berliner Starttag. Höchstens 100 Karten insgesamt; ist die Grenze erreicht, wird mit `truncated: true` gekürzt. Abgesagte und verschobene Events bleiben mit ihrem `status` in den Listen (P01: sichtbar mit Text "Abgesagt").

### 2.5 `GET /api/public/categories`

`PublicCategoryOut[]`: `{slug, name, kind, parentSlug, description, upcomingCount}` für aktive Kategorien in `sort`-Reihenfolge (Eltern vor Kindern); `upcomingCount` zählt kommende Events der Kategorie und ihrer Kinder (`ends_at >= now`). Kategorien mit Zähler 0 stehen drin (P07 braucht sie), die Chips auf P01 filtern sie client-seitig heraus.

### 2.6 `GET /api/public/calendar?month=YYYY-MM[&category=<slug>]`

`month` Pflicht und im Bereich -24 bis +24 Monate um heute (sonst 422). `PublicCalendarOut {month, truncated, days: [{date, count, items: PublicCalendarEntry[]}]}`; `PublicCalendarEntry {slug,title,startsAt,endsAt,allDay,startsOn,endsOn,status,categorySlug}`. Ein mehrtägiges Event steht an jedem Berliner Tag, den es berührt. Höchstens 300 Events je Monat, darüber `truncated: true`. Das Raster (ab `narrow`) und die Agenda (Handy) lesen dieselbe Antwort.

### 2.7 `GET /api/public/archive[?year=YYYY&category=<slug>&limit=&cursor=]` (Rückblick)

Vergangene öffentliche Events **mit Poster** (`ends_at < now` und `hero_sha IS NOT NULL`); die View führt keinen Zustand, "archiviert" ist hier "vorbei" (der Worker archiviert 12 h nach dem Ende, M5b 2.5; die Differenz ist unerheblich). `PublicArchiveOut {years: int[], year, items: PublicEventCard[], nextCursor}`: `years` absteigend, Standardjahr das jüngste mit Treffern, `limit` 1 bis 48 (Standard 24), Sortierung `starts_at desc`, Cursor wie 2.2.3 (Keyset, absteigend). Gruppierung nach Semester (WS/SoSe) macht der Client aus `startsAt`. Freie Textsuche im Rückblick läuft über `GET /api/public/events?past=1` mit denselben Filtern.

### 2.8 `GET /ics/e/{slug}.ics`, HTML-Hülle, Sitemap, robots

**Einzel-ICS** (`ics_router.py`): dieselbe Schreibkette wie `all.ics` (`ics/writer.build_calendar`, UID, SEQUENCE, UTC-`Z`, kein VTIMEZONE), eine Zeile aus der View ohne Zeitfenster (ein vergangenes Event bleibt abrufbar), `X-WR-CALNAME` = Titel. Header: `Content-Type: text/calendar; charset=utf-8`, `Content-Disposition: attachment; filename="<slug>.ics"` (der Knopf "In Kalender" lädt/öffnet, die Abos bleiben `inline`), `Cache-Control: public, max-age=300`, `ETag`/304. Slug-Muster wie 2.3, unbekannt 404. Nicht im Worker-Snapshot (eine Zeile, live), aber im Antwort-Cache (2.10).

**HTML-Hülle** (`shell/router.py`), Antworten `text/html; charset=utf-8`:

| Pfad | Titel (`<title>`, `og:title`) | Beschreibung | Status |
|---|---|---|---|
| `/` | "Heute am Campus · STUPA Events" | fester Satz | 200 |
| `/suche` | "Suche · STUPA Events" | fester Satz; `?q=` ändert nichts (Cache, Log) | 200 |
| `/kalender` | "Kalender · STUPA Events" | fester Satz | 200 |
| `/rueckblick` | "Rückblick · STUPA Events" | fester Satz | 200 |
| `/e/{slug}` | Titel des Events (mit Präfix "Abgesagt: " / "Verschoben: ") | "Do., 22. Okt. 2026, 20:00 · Ort. Summary" auf <= 200 Zeichen | 200, unbekannt 404 mit SPA-Hülle und `noindex` |
| `/k/{slug}` | "<Name> · STUPA Events" | Kategorienbeschreibung, sonst fester Satz | 200, unbekannt 404 wie oben |

Die übrigen SPA-Routen (`/abos`, `/impressum`, `/datenschutz`, `/offline`, alles Unbekannte) bedient weiter der nginx-Fallback mit dem statischen `index.html` (Angular rendert die 404 selbst). Die Hülle liest das gebaute `index.html` aus `SPA_INDEX_PATH` (neue Einstellung, Standard `/app/spa/index.html`, ergänzt in `.env.example` und im Paritätstest `test_env_example_settings_parity.py`), cacht den Inhalt im Prozess nach `mtime` und ersetzt **nur** `<title>`, `<meta name="description">` und fügt vor `</head>` den Block ein: `<link rel="canonical">`, Open Graph (`og:type`=`website`, `og:site_name`, `og:locale`=`de_DE`, `og:title`, `og:description`, `og:url`, `og:image` samt `og:image:width`/`height`/`alt`), `twitter:card`=`summary_large_image`, `<link rel="alternate" type="text/calendar" href="/ics/all.ics" title="Alle Events">` (auf `/k/…` zusätzlich der Kategorie-Kalender, auf `/e/…` der Einzel-ICS), bei Events das JSON-LD. Dazu eine `<noscript>`-Liste (bei `/` die heutigen und nächsten Events als Links, bei `/k/` die kommenden, bei `/e/` die Eckdaten). Erzeugt wird alles über Jinja2 mit Autoescape (`jinja2>=3.1` steht in `pyproject.toml`); kein String-Bauen von Hand. Fehlt die Datei: 503 Problem+JSON `spa_not_built`.

- `og:image` = Derivat `og_1200x630` des Posters (absolute URL `public_base_url` + `/api/public/media/<id>.webp`, derselbe Pfad wie `image.url` im Feed, PLAN §8.1); ohne Poster `{public_base_url}/og-default.png` (L18). `og:url` und `canonical` sind `public_base_url` + Pfad, ohne Query.
- **JSON-LD** (`shell/jsonld.py`) nur auf `/e/…`: `@type: Event`, `name`, `startDate`/`endDate` als ISO 8601 mit Berliner Offset (ganztägig nur Datum), `eventStatus` (`https://schema.org/EventScheduled|EventCancelled|EventPostponed`), `eventAttendanceMode: OfflineEventAttendanceMode`, `location` `Place{name, address: PostalAddress{streetAddress, addressLocality}}` nur wenn `venue` vorhanden und nur die öffentlichen Felder, `organizer` `Organization{name}`, `image` [og-URL], `description` (Summary), `url`, `inLanguage: de`, `offers` `Offer{url: ticket_url}` **nur wenn** `ticket_url` gesetzt (kein Preis, `cost_text` ist Freitext). Serialisierung mit `json.dumps`, danach `<`, `>`, `&`, U+2028, U+2029 als `<`, `>`, `&`, ` `, ` `; Ausgabe in `<script type="application/ld+json">` (ein Datenblock, wird nicht ausgeführt, die SPA-CSP ohne `script-src` für Inline ist damit kein Hindernis; **die Prüfung im Browser ohne CSP-Verstoß steht in 6.3**).
- Die Hülle hängt **nicht** vom User-Agent ab (derselbe Körper für Matrix, WhatsApp, Browser; Test in 6.3).
- Header der Hülle: `Cache-Control: public, max-age=60, stale-while-revalidate=30`, `ETag` (Hash des Körpers)/304, `Content-Security-Policy` (der SPA-Wert aus `deploy/web/security-headers.conf`, als Konstante `SPA_CSP` in `shell/page.py`; `SecurityHeadersMiddleware` setzt nur Fehlendes, ein Routen-Header gewinnt), `Referrer-Policy: strict-origin-when-cross-origin`, `X-Content-Type-Options`, kein `Set-Cookie`. Hinter nginx versteckt `api-proxy.conf` die API-Header (`proxy_hide_header`), nginx setzt seinen identischen Satz: genau ein CSP-Header je Route, was `deploy/smoke.sh` prüft. PLAN §8.4 verlangt dafür eine nginx-Ausnahme "nur X-Frame-Options"; sie ist **nicht nötig**, weil die Locations in `nginx.conf` schon `security-headers.conf` einbinden und die Hülle denselben CSP-Wert trägt (8.4).

**Sitemap** (`GET /sitemap.xml`, `application/xml; charset=utf-8`): `/`, `/suche`, `/kalender`, `/abos`, `/rueckblick`, jede aktive Kategorie `/k/<slug>`, jedes öffentliche Event `/e/<slug>` mit `<lastmod>` (= `updated_at`, UTC `Z`). Fenster: Events mit `ends_at` ab 12 Monate zurück; höchstens 45 000 URLs (Sitemap-Grenze 50 000), darüber werden die ältesten gekappt und `snapshot_too_large` geloggt. Gebaut vom Worker als Snapshot `sitemap` in `rebuild_public_cache` (gleiche `version`-Prüfung wie Feed/ICS, `cache.SNAPSHOT_TTL_SECONDS`), live aus der View, wenn der Snapshot fehlt (`serving`-Muster). `Cache-Control: public, max-age=3600`.

**robots.txt** (`text/plain`, `max-age=3600`): `User-agent: *`, `Allow: /e/`, `Allow: /k/`, `Allow: /suche`, `Disallow: /api/`, `Disallow: /ics/`, `Disallow: /dossiers`, `Disallow: /verwaltung`, `Disallow: /konto`, `Disallow: /login`, `Sitemap: <public_base_url>/sitemap.xml`. PLAN §8.4 nennt nur `/api/` und `/ics/` als Verbot; die internen App-Pfade sind eine Ergänzung (sie liefern ohnehin die SPA-Hülle, indexieren soll sie niemand).

### 2.9 Cookie-Freiheit

`CsrfMiddleware` (`middleware.py`) setzt das XSRF-Cookie heute auf jeder Antwort ohne Cookie. Neu: **nur wenn die Anfrage das Session-Cookie trägt oder die Antwort es setzt** (`settings.session_cookie_name` in `request.cookies` oder im `Set-Cookie` der Antwort, etwa nach dem OIDC-Callback). Ein anonymer Besucher bekommt damit nie ein Cookie, auch nicht durch den `GET /api/auth/me` der SPA. Der Bearer-/Session-Pfad für Schreibzugriffe bleibt unverändert (`_has_auth_cookie`). Zusätzlich zählen die Hülle-Pfade als öffentlich: `PUBLIC_PREFIXES` bekommt keine Pfade dazu (das würde `noindex` auf die Hülle legen), sondern eine zweite Funktion `is_cookie_free_path()` in `shared/errors.py` für `PUBLIC_PREFIXES` plus `/`, `/suche`, `/kalender`, `/rueckblick`, `/e/`, `/k/`, `/sitemap.xml`, `/robots.txt`. Anpassen: `tests/unit/test_middleware.py` und `tests/unit/publicapi/test_public_no_set_cookie.py` (heute pinnt er den Präfix `/api/public/`).

### 2.10 Cache, Invalidierung, Rate-Limit

**Antwort-Cache** (`respcache.py`): Schlüssel `events:public:resp:<sha256(Pfad + sortierte, normalisierte Query)>`, Wert = Hash `{version, etag, body, contentType, generatedAt}`, `TTL` je Route (Suche, Liste, Heute, Kalender, Detail, Rückblick, Hülle: 60 s; Kategorien: 300 s; Einzel-ICS: 300 s). Gültig nur, wenn `version` dem Zähler `events:feed:version` entspricht (`events/postcommit.FEED_VERSION_KEY`, derselbe Zähler wie bei Feed und ICS). Den Zähler erhöht `invalidate_feed_cache` bei `publish`, `unpublish`, `archive`, `restore`, `cancel`, `postpone`, `reinstate`, Änderungen an einem öffentlichen Feld, Format-/Kategorie-/Orts-/Organisations-Änderungen (`invalidate_public`, M5b 2.2 und `test_cache_invalidation.py`); damit sind alle neuen Antworten bei jeder dieser Aktionen sofort ungültig. Zeitabhängige Antworten (`today`, `calendar`, "kommend" in `categories`) altern zusätzlich über das 60-Sekunden-TTL. Redis-Fehler und fehlender Pool sind ein Cache-Fehlschlag, nie ein 500 (Muster `cache.load`). Ein Bauen bei Fehlschlag schreibt zurück (`SET` mit `EX`); keine Sperre gegen Stampede (das fängt `proxy_cache_lock` in nginx, 5.1). **Gebaut wird nur für 200**; 4xx werden nie gecacht.

**HTTP-Caching:** `ETag` (strong, Hash des Körpers), `If-None-Match` -> 304 (`publicapi/etag.matches`), `Cache-Control: public, max-age=60, stale-while-revalidate=30` (Kategorien und Einzel-ICS `max-age=300`). `HEAD` wie `GET`.

**Rate-Limit** (`ratelimit.py`, Redis-Sliding-Window `shared/ratelimit.RedisRateLimiter` über `antiabuse.get_rate_limiter`, fail-open wie überall): Schlüssel `public:ip:<client_ip>` und `public-search:ip:<client_ip>`; neue Einstellungen `rl_public_per_minute=120`, `rl_public_search_per_minute=30` (`settings.py`, `.env.example`, Paritätstest). Antwort bei Überschreitung: 429 Problem+JSON `rate_limited` mit `Retry-After`. **Gezählt werden nur Cache-Fehlschläge**: der Limiter läuft im Bauer, nicht davor. Begründung: ein Treffer aus Redis kostet fast nichts, und hinter einer Campus-NAT teilen viele Nutzende eine IP (die Kommentare in `middleware.py` und `antiabuse.py` nennen das ausdrücklich); 120 Treffer pro Minute pro IP würden dort zu früh blockieren. Den Schutz der billigen Treffer übernimmt `limit_req` in nginx (10 r/s, Burst 20). Die Suche (`q` gesetzt) zählt zusätzlich gegen die 30/min. Nicht begrenzt in der App: Feed, ICS, `media` (immutable, nginx-begrenzt). Das ist eine Abweichung vom Wortlaut "120/min je IP" (8.3).

## 3. Frontend: Public-Shell und Screens

Pfade: `frontend/src/app/features/public/**` für die Seiten, `layout/public-header`, `layout/public-bottom-bar`, `layout/site-footer` für den Rahmen. Standalone, OnPush, signals, getrennte `.html`/`.scss`, Kit-Tokens (`--color-*`, `--space-*`, Radien aus dem Kit), keine eigenen Hex-Werte (`core/theme/token-roles.spec.ts` prüft Rollen), hell und dunkel über `data-theme`. Neue Texte in `core/i18n/translations.public.de.ts` (`publicDe`, in `translations.ts` eingehängt), Gendern mit Doppelpunkt oder neutral.

### 3.1 Rahmen und Routen

- `ShellFrame`: Routen-Daten `frame: 'public'` erzwingen den Rahmen `public`, **auch mit Session**. Eine angemeldete Person, die `/e/<slug>` aus einer Mail öffnet, sieht dieselbe öffentliche Seite; der Header zeigt ihr statt "Anmelden" den Link "Zum Dossier" (`/dossiers`). Die tiefste Route gewinnt (Muster der vorhandenen `wide`/`footer`-Daten in `shell.component.ts`). Der Rahmen `pending` bleibt, solange `/auth/me` nicht antwortete.
- `/` ist öffentlich und **kein Redirect mehr**; `homeRedirectGuard`, sein Spec, `pages/home/` und die Schlüssel `home.*` fallen weg. Der Anmelden-Knopf des Headers ruft `auth.login('/dossiers')` (nach dem Login landet man im Dossier, nicht auf der öffentlichen Startseite; `loginReturnTo` verwirft den Startseitenpfad ohnehin, `auth.service.ts`). Ein `goto('/')` kommt in `frontend/e2e` und `frontend/src` nicht vor (gegrept); ob Login-Helfer in `e2e/support` auf die Weiterleitung von `/` nach `/dossiers` warten, habe ich nicht gelesen (**Builder prüft**, `m1` bis `m5b` müssen grün bleiben).
- Routen (`app.routes.ts` ruft `PUBLIC_ROUTES` aus `features/public/public.routes.ts`, **vor** den Feature-Routen und dem `**`-Fallback; alle mit `data: {frame: 'public', footer: true}`):

| Pfad | Seite | Titel-Schlüssel |
|---|---|---|
| `` | P01 Heute | `public.today.title` |
| `suche` | P02 Suche | `public.search.title` |
| `kalender` | P03 Kalender | `public.calendar.title` |
| `e/:slug` | P04 Detail | Eventtitel (dynamisch) |
| `k/:slug` | P05 Kategorie | Kategoriename |
| `rueckblick` | P13 Rückblick | `public.review.title` |
| `abos` | P07 Abos | `public.subscribe.title` |
| `impressum`, `datenschutz` | Platzhalter | `public.legal.*` |
| `offline` | P14 Offline | `public.offline.title` |
| `**` | P14 404 (öffentliche Variante des vorhandenen `not-found.component`) | `public.notFound.title` |

  Der Seitentitel wird je Navigation über `Title` gesetzt ("<Name> · STUPA Events"). `campus-heute` (P10) ist **keine eigene Route** in B1: der Block "Heute am Campus" von P01 ist P10 ohne Dauerangebote (8.5).
- `homeRedirectGuard`-Nachfolger gibt es nicht. Die interne Startseite bleibt `/dossiers`.

### 3.2 Header, Footer, Navigation

- **Header** (`app-public-header`): Marke (Wortmarke, Phone: Marke allein) mit Link `/`, Titel "STUPA Events" als sichtbarer Text neben der Marke ab `narrow`; Navigation **Heute · Suche · Kalender · Abos** als `nav` mit `aria-label`, `routerLinkActive` und `aria-current="page"` (ab `narrow`, auf dem Handy entfällt sie, dort trägt die Bottom-Bar); rechts Theme-Schalter (vorhanden), "Anmelden" (anonym) oder "Zum Dossier" (angemeldet). Dazu die Suchpille (`app-search-pill`) ab `wide`, öffnet `/suche`.
- **Footer** (`app-site-footer`): zeigt in `public` die CI-Zeile (`footer.coBranding` bleibt), Links **Impressum**, **Datenschutz**, **Kalender abonnieren** (`/abos`) und **Intern anmelden** (ruft `auth.login('/dossiers')`; angemeldet: "Zum Dossier"). Impressum und Datenschutz sind Platzhaltertexte ("Dieser Text wird mit der Hochschule und der Datenschutzbeauftragten abgestimmt und ergänzt."), kein erfundener Inhalt.
- **Bottom-Bar (Phone, `<= 768`, Kit-`MEDIA.phone`)**: neue Komponente `layout/public-bottom-bar`, vier Einträge **Heute** (`/`, Icon `home`), **Suche** (`/suche`, `search`), **Kalender** (`/kalender`, `cal`), **Abos** (`/abos`, `bell`); `nav`-Landmark mit Label, `ariaCurrentWhenActive`, Touch-Ziele 44 x 44 px, Safe-Area unten (`env(safe-area-inset-bottom)`). Sie ersetzt die interne Bottom-Bar nur im Rahmen `public`. Das weicht von PLAN 8.6 ab (dort "Karte/Campus heute" als dritter Platz, "Suche" in Heute eingebettet; 8.4).

### 3.3 API-Schicht und Zustand

`features/public/api/public-api.service.ts` (HttpClient, nur wurzelrelative `/api/public/...`-URLs), `features/public/model/public.models.ts` (Typen spiegeln 2.2 bis 2.7, camelCase). Der `authInterceptor` setzt für `/api/`-URLs `withCredentials`, ohne eine Anmeldung zu verlangen: `skipReloginOn` kennt `/api/public/` schon (kein Relogin bei 401). Seitenzustand in Signalen; Filter, Suchtext, Monat und Jahr leben in den **Query-Parametern der URL** (teilbar, Zurück-Taste funktioniert), gelesen über `withComponentInputBinding`/`queryParamMap`. Live-Suche mit 250 ms Entprellung, laufende Anfragen werden bei neuer Eingabe verworfen (`switchMap`). Zeiten ausschließlich über `formatEventTime(iso, 'Europe/Berlin')` aus `shared/event-time.ts` (L15), nie über Browser-Zeitzone oder UTC-Helfer. Ladezustand: `app-skeleton`, nie Spinner; die globale Load-Bar bleibt.

### 3.4 Screens

Für alle: Fehlerzustand "Die Termine konnten nicht geladen werden. [Neu laden]" (`app-note` mit Knopf, `role="alert"`), 429 "Zu viele Anfragen. Bitte warte einen Moment.", Leerzustand mit `app-empty-state` (ein Satz, eine Aktion). Abgesagt/verschoben erscheint **als Text** mit `app-status-text` ("Abgesagt", "Verschoben", Grund aus `statusReason.text`), nie nur als Farbe oder Durchstreichung. Bilder: `<img>` mit `width`/`height` aus der Antwort, `loading="lazy"` (das Hero-Bild auf P01 und das Poster auf P04 `fetchpriority="high"`, nicht lazy), `decoding="async"`, `alt` aus `image.alt` (leer = dekorativ, `alt=""`), Fehler fällt auf einen Platzhalter zurück (Muster `ImageThumbComponent`, `failed`-Signal). Ohne Poster: Platzhalterfläche im Seitenverhältnis 1200:630 mit Kategorie-Icon, kein Bildhinweis an Besucher:innen.

- **P01 Heute** (`/`): Suchpille oben (öffnet `/suche`), Hero-Karte mit dem nächsten Event (erstes nicht abgesagtes aus `today` ∪ `days`; Poster `card`, Titel, Datum/Uhrzeit, Ort, Kategorie-Tag, Link), darunter "Heute am Campus" (`today`, `app-list-item` mit `app-date-block`) und "Diese Woche" (`days` mit Tageskopf "Do., 22. Okt."), Kategorie-Chips (`app-filter-select`-Muster, aus `categories` mit `upcomingCount > 0`; Klick führt nach `/suche?category=<slug>`), Link "Kalender abonnieren" (`/abos`). Leer: "Heute ist nichts geplant. Schau in den Kalender für die nächsten Tage." mit Knopf "Zum Kalender". Offline-Hinweis erst ab B4. **Der Get-started-Teaser entfällt** (P06 fehlt).
- **P02 Suche** (`/suche?q=&category=&organization=&from=&to=&past=`): Suchfeld (`app-search-pill`, Vorschläge: beim Fokus ohne Eingabe die Kategorien als Chips; Trefferschnellvorschau gibt es nicht, die Liste darunter ist die Live-Antwort), Facetten-Chips (Zeitraum heute/Wochenende/7 Tage/Monat, Kategorie, Organisation) mit Zählern aus `facets`; Auswahl öffnet am Desktop ein Menü (`app-filter-select`), am Handy ein Bottom-Sheet (`app-side-sheet side="bottom"`, 4.2). Trefferkarten: Poster-Thumb (`thumb`, 96 x 54 px, `loading="lazy"`), Datum (`app-date-block`), Titel, Ort, Kategorie-Tag, Status als Text. Nachladen: Knopf "Mehr anzeigen" über `nextCursor` (kein Endlos-Scroll; Tastatur- und axe-freundlich). Leer: "Nichts gefunden für „{q}“ in diesem Zeitraum." mit Knöpfen "Zeitraum erweitern" (entfernt `from`/`to`) und "Filter zurücksetzen". Fehler 422 `query_too_long`: "Suchbegriff zu lang."
- **P03 Kalender** (`/kalender?month=YYYY-MM&category=`): ab `narrow` das Monatsraster (`app-calendar-grid` aus `shared/ui`, `role="grid"`, Pfeiltasten, "+N"-Zelle ab drei Einträgen, Klick auf einen Tag öffnet dessen Liste im Seitenpanel "Kommende"), Phone: Agenda nach Tagen (aus derselben Antwort `days`). Monatswechsel Pfeile + "Heute"; Kategorie-Filter als Chip; Knopf "Diesen Kalender abonnieren" (`/abos#k=<slug>` bzw. `/abos`). Leer: "In diesem Monat ist nichts eingetragen." Das Raster wird über `GridEntry`-Adapter aus `PublicCalendarEntry` gespeist (Builder prüft die Eingabe-Signatur von `calendar-grid.component.ts`: `entries`, `mode`, `anchor`, `entryOpen`, `rangeChange`, `anchorChange`).
- **P04 Detail** (`/e/:slug`): Poster groß (`card`, volle Spaltenbreite, `alt`, darunter `credit`), Titel (`h1`), Status-Banner (`app-note`, Text "Abgesagt: Raum nicht verfügbar" / "Verschoben, neuer Termin folgt") **vor** dem Titelblock, Eckdaten als Definitionsliste (Wann in Berliner Zeit "Do., 22. Okt. 2026, 20:00 bis 22:30 Uhr", Wo mit Name/Adresse oder "Treffpunkt auf Anfrage", Veranstalter, Kategorien als Links auf `/k/<slug>`, Kosten, Webseite), Kurztext, `descriptionHtml` über `[innerHTML]` (Angular sanitisiert zusätzlich), Knöpfe **"In Kalender"** (Link auf `icsUrl`, `download`-Attribut, lädt `GET /ics/e/<slug>.ics`), **"Ticket"** (nur mit `ticketUrl`, externer Link `rel="noopener noreferrer"`, kein Request beim Laden), **"Teilen"** (`navigator.share`, falls vorhanden, sonst Link in die Zwischenablage mit Toast "Link kopiert."; scheitert das Kopieren: "Link konnte nicht kopiert werden. Markier ihn bitte von Hand." mit lesbarer URL), Block "Mehr aus dieser Reihe" aus `more`, "Ähnliche abonnieren" -> `/abos#k=<hauptkategorie>`. Vergangen (`isPast`): `app-note` "Diese Veranstaltung ist vorbei." mit Link `/rueckblick`. 404: "Diese Veranstaltung gibt es nicht oder sie ist nicht mehr verfügbar." (P04 sieht zusätzlich 410 vor, 8.2.) Die Hülle (2.8) liefert für denselben Pfad den Kopf; die SPA bootet aus derselben `index.html` und holt die Daten erneut (kein State-Transfer, Annahme: ein zweiter, gecachter Request ist billiger als Hydration).
- **P05 Kategorie** (`/k/:slug`): Name, Beschreibung, Knopf "Kalender abonnieren" (Link `/abos#k=<slug>`), kommende Events der Kategorie (`GET /events?category=<slug>`, `app-list-item`), darunter "Rückblick" (`?past=1&limit=6`). Leer: "Gerade nichts geplant in {Name}. Abonniere, dann siehst du neue Termine im Kalender." 404 für unbekannten Slug.
- **P07 Abos** (`/abos`, Anker `#k=<slug>` scrollt und hebt die Zeile hervor): Hinweis oben "Änderungen kommen mit Verzögerung an (bis zu einem Tag, je nach Kalender-App)." (`app-note`), Abschnitt "Alles in einem Kalender" mit `webcal://<host>/ics/all.ics` als Knopf **"In Kalender-App öffnen"**, der `https://…`-URL in einem Feld mit Knopf **"Kopieren"** (URLs nie gekürzt, `overflow-wrap:anywhere`); Abschnitt "Kategorien" je Zeile Name, Beschreibung, "Kalender öffnen" (`webcal://…/ics/k/<slug>.ics`), "Kopieren"; Anleitung (Akkordeon oder Absätze) für Google ("Am Computer unter Weitere Kalender, Per URL hinzufügen"), Apple und Thunderbird; "Per Mail" ist ein deaktivierter Knopf mit Text "kommt bald"; "Persönliches Profil" ebenso. Kopieren über `navigator.clipboard.writeText`, bei Fehler der Hinweistext oben. Keine QR-Codes (der Plan nennt `app-qr-code` für P07; ohne Server-Matrix und Kit-Komponente spare ich sie in B1, 8.6).
- **P13 Rückblick** (`/rueckblick?year=`): Jahr-Chips aus `years`, Poster-Raster (`card`-Thumb, Titel, Datum; 1 Spalte Phone, 2 `narrow`, 3 `wide`), Gruppenköpfe "Wintersemester 2025/26" / "Sommersemester 2026" (WS ab 1. Oktober bis 31. März, SoSe ab 1. April bis 30. September, nach Berliner Beginn), Knopf "Mehr anzeigen". Leer: "Noch kein Rückblick vorhanden."
- **P14** `/offline` ("Du bist offline. Zuletzt geladene Termine siehst du unter Heute."), 404 ("Diese Seite gibt es nicht. [Zur Startseite]"), Impressum und Datenschutz (Platzhalter). Der Update-Hinweis der PWA (`app-sw-update-prompt`) existiert (`SwUpdatePromptComponent`) und bleibt unverändert.

### 3.5 Keine externen Requests

Es gibt keine Schriften, Karten, Skripte, Analytics oder Bilder von fremden Origins. Schriften kommen aus dem Kit (IBM Plex, selbst gehostet unter `/assets/fonts/ibm-plex-*.woff2`, laut `vendor/ui-kit/src/styles/index.scss`), Icons sind Inline-SVG des Kits. Externe Ziele (Ticket, Webseite) sind nur Links. CSP `connect-src 'self'; img-src 'self' data: blob:` ändert sich nicht. Ein Playwright-Test prüft das (6.2).

## 4. Handy-UX (390 x 844)

1. **Layout:** ein Spalte, Seitenrand 16 px, kein horizontales Scrollen (Test: `document.documentElement.scrollWidth <= innerWidth` auf jeder Route). Breakpoints: `phone <= 768` (Kit), Monatsraster ab `narrow`.
2. **Touch-Ziele >= 44 x 44 px** für Navigationseinträge, Chips (Mindesthöhe 44 px, auch wenn das Mock `32 px` zeigt; der Kontrakt folgt WCAG 2.5.8 und der Aufgabe), Knöpfe, Listenzeilen, Kalenderzellen im Agenda-Modus. Test: Playwright misst `boundingBox()` aller `a, button, [role=button]` im sichtbaren Bereich auf 390 px und schlägt unter 44 px fehl (Ausnahme: Fließtext-Links im Beschreibungstext).
3. **Facetten als Bottom-Sheet:** auf dem Handy öffnet ein Chip oder der Knopf "Filter ({n})" ein `app-side-sheet` mit `side="bottom"`: Griff, Überschrift, Abschnitte (Zeitraum als Chips, Kategorie und Organisation als Checkbox-Liste mit Zähler), Fuß mit "Zurücksetzen" und "{n} Treffer anzeigen". Fokusfalle, `Esc` und Scrim schließen, Fokus kehrt zurück. Die Auswahl wirkt live in der URL, das Sheet schließt nichts ohne Nutzeraktion.
4. **Kein Pull-to-refresh** (`overscroll-behavior-y: contain` auf dem Hauptbereich, kein eigener Mechanismus); neu laden geht über den "Neu laden"-Knopf im Fehlerzustand und den Browser.
5. **Kein `maximum-scale`/`user-scalable=no`** (WCAG 1.4.4); `index.html` hat nur `width=device-width, initial-scale=1, viewport-fit=cover` (Ist, bleibt). Texteingaben mit `font-size >= 16px` (kein iOS-Zoom).
6. **Bottom-Bar** deckt den Inhalt nicht ab: Hauptbereich bekommt `padding-bottom` in Höhe der Leiste plus Safe-Area; Toasts liegen darüber.
7. **Hell/Dunkel:** `theme-init.js` (L17) setzt `data-theme` vor dem ersten Paint; Kontrast nach Kit-Tokens, axe prüft beide Themen.
8. **Skeletons statt Layout-Sprung:** Karten haben feste Seitenverhältnisse (Poster `aspect-ratio: 1200/630`, Thumb `16/9`).

## 5. Lastschutz, Deploy, Compose-Lint

### 5.1 nginx (`deploy/web/nginx.conf`, `snippets`)

Jede Location bindet weiter `security-headers.conf` ein (Lint unten). Änderungen:

1. **Neue API-Pfade:** `location = /` (exakt, an die API; sonst gewinnt `location /` mit `try_files`), `location = /kalender`, `location = /rueckblick`; Muster wie `= /suche` (`limit_req zone=ev_page burst=10 nodelay`, `client_max_body_size 1k`). Die Map `$ev_cache_control` bekommt für `/`, `/kalender`, `/rueckblick` den Wert `""`, damit der `Cache-Control` der API ungestört durchgeht (heute ist der Standard `no-cache`; `= /` fiele sonst auf `no-cache`).
2. **`/index.html` und alle SPA-Routen** bleiben beim statischen Fallback (`try_files`), `no-cache` wie bisher.
3. **Log ohne Query überall:** Server-Block `access_log /var/log/nginx/access.log ev_noquery;` als Standard; die Locations mit eigenem `access_log` (`/ics/p/` redigiert, `/healthz` aus) behalten ihres. Damit steht `/suche?q=…` nie im Log (L12). `error_log` schreibt die Anfragezeile nur bei Fehlern; Builder prüft in der Compose-Probe, dass nach `curl '/suche?q=GEHEIM'` der String nirgends im Container-Log steht (`docker logs`).
4. **`proxy_cache`:** `proxy_cache_path /var/cache/nginx/ev levels=1:2 keys_zone=ev_pub:5m max_size=64m inactive=10m use_temp_path=off;` (Datei-Kopf, `http`-Kontext der conf.d-Datei), in den cachefähigen Locations (`/api/public/` ausgenommen `media`, `= /`, `= /suche`, `= /kalender`, `= /rueckblick`, `/e/`, `/k/`, `/ics/` ausgenommen `/ics/p/`, `= /sitemap.xml`, `= /robots.txt`): `proxy_cache ev_pub; proxy_cache_valid 200 60s; proxy_cache_lock on; proxy_cache_use_stale error timeout updating; proxy_cache_key "$host$uri$is_args$args"; proxy_set_header Cookie ""; proxy_ignore_headers Set-Cookie;` (nie ein Cookie nach oben, nie eines zurück). `/ics/p/` bleibt ungecacht (B3). Der `MEM`: `web` hat `mem_limit 64m` (Compose); `keys_zone=5m` plus Seitencache im Dateisystem passt (Builder prüft `docker stats` unter Last).
5. **`gzip on`** für `application/json text/html text/calendar application/xml text/plain` (heute nicht gesetzt; `gzip_min_length 512`, `gzip_vary on`). Annahme: spart auf dem Handy spürbar; nicht gemessen.
6. **Bild-Cache:** `/api/public/media/` liefert `immutable` (vorhanden); nginx behält das, kein `proxy_cache` nötig (Browser-Cache).
7. **`limit_req`/`limit_conn`** bleiben (`ev_public` 10 r/s Burst 20, `ev_page` 5 r/s Burst 10, `ev_conn` 20). Hinweis: `= /` bekommt `ev_page`; ein Mobilfunk-Burst beim Laden der SPA (HTML + ~20 Bundles) trifft nur den HTML-Teil, die Bundles laufen über `location /` ohne Limit.
8. **`security-headers.conf`** bleibt unverändert (CSP aus PLAN 11.2).

### 5.2 Docker

- Das API-Image bekommt das gebaute `index.html` (PLAN 8.4, Multi-Stage): `backend/Dockerfile` erhält eine Stufe `spa` (`FROM node:24-alpine`, baut das Frontend wie `deploy/web/Dockerfile`), und `COPY --from=spa /app/dist/*/browser/index.html /app/spa/index.html`. Das verlangt den Build-Kontext Repo-Wurzel für `api`/`worker`/`migrate` (`build: {context: .., dockerfile: backend/Dockerfile}` im Anker `*backend` von `docker-compose.yml`; Builder prüft `.dockerignore`). Alternative, falls zwei Frontend-Builds zu teuer sind: eine gemeinsame benannte Stufe in einer `docker-bake`-/BuildKit-Cache-Mount-Konstruktion. Die Mindestforderung ist ein **Test statt einer Konstruktion**: Hülle und `/index.html` (nginx) nennen dieselben Bundle-Dateinamen (6.3).
- `PUBLIC_BASE_URL` (heute `http://localhost:8081`) bleibt der Ursprung für `canonical`, `og:url`, `og:image`, Sitemap und JSON-LD; in Prod `https://events.reutlingen.university` (Domain-Vorschlag aus ENTSCHEIDUNGEN Nr. 2, **nicht** bestätigt).
- Dev ohne Compose: `SPA_INDEX_PATH` zeigt auf `frontend/dist/stupa-events/browser/index.html` (`deploy/.env.host.example`, Annahme: nach `npm run build` vorhanden, `frontend/dist/stupa-events` liegt im Arbeitsbaum). Unter `ng serve` (4200) gibt es die Hülle nicht (der Dev-Proxy `proxy.conf.json` leitet nur `/api`); die Hülle wird gegen die Compose-`web` geprüft (6.3). In `proxy.conf.json` kommt deshalb nur `/ics` dazu (Download des Einzel-ICS im Playwright-Test); `/e`, `/k`, `/sitemap.xml` und `/robots.txt` werden dort **nicht** proxied, damit SPA-interne Navigation auf `/e/x` unter `ng serve` bei der SPA bleibt.

### 5.3 Compose-Lint und Smoke

- `deploy/compose-lint.sh` (gilt weiter: Projektname, Ports, `mem_limit`, jede Location mit CSP-Include, kein Prune) wird erweitert um: (a) jeder `location` mit `proxy_cache` setzt `proxy_set_header Cookie ""`; (b) der Server-Standard-`access_log` nutzt `ev_noquery` und keine Location außer `/ics/p/` hat ein anderes Format; (c) `docker-compose.yml` enthält keine zweite Veröffentlichung von Port 80 und `web` behält `172.29.10.10`; (d) `mem_limit` der neuen Dienste (keine neuen Dienste, nur die Prüfung bleibt grün).
- `deploy/smoke.sh`: Pfadliste um `/kalender`, `/rueckblick`, `/ics/e/probe.ics` ergänzen; weiterhin genau ein Header je Sicherheitsheader und CSP auf jedem Pfad.
- `deploy/public-smoke.sh` (neu, 6.3): Link-Vorschau-, Cookie-, Log-Probe gegen die laufende Compose-`web`.

## 6. Tests

### 6.1 Backend (`backend/tests/`)

Unit (`tests/unit/publicapi/`): Parameterparser (Datum, Mehrfachwerte, Grenzen, `q`-Fehler), Cursor beider Formen, Facetten-Bau (disjunktiv), Zeilen -> Karte/Detail (Bilder, Status, Ort "Treffpunkt auf Anfrage", leere Kategorie), Berliner Tagesgrenzen über die Sommer-/Winterzeit-Umstellung (letzter Sonntag im März/Oktober), Semester-Zuordnung, JSON-LD (Escapes `<`, `>`, `&`, U+2028/9, `EventCancelled`/`EventPostponed`, `offers` nur mit Ticket), Meta-Bau (Länge, Autoescape eines Titels mit `<script>`), `robots.txt`, `Sitemap`-Bytes (XML wohlgeformt, `lastmod`, Kappung), Respcache (Version-Abgleich, Redis-Ausfall = Fehlschlag), Rate-Limit (Fehlschlag zählt, Treffer zählt nicht, 429 mit `Retry-After`), `is_cookie_free_path`.

Integration (`tests/integration/publicapi/`, `-m integration`, echte Postgres/Redis wie bisher):

1. **Nur `events_public`:** ein Test importiert alle Module unter `publicapi/` (rekursiv) und prüft über `ast`, dass kein Modul `get_session`/`DbSession`/`app.db` oder ein ORM-Modell (`app.modules.*.models`) importiert und dass jede Route des `site_router`, `ics_router` und `shell.router` `get_public_session` als Abhängigkeit trägt (OpenAPI-Dependency-Inspektion). Ergänzt `test_route_authz_inventory.py` um die neuen Pfade als "öffentlich, ohne Principal".
2. **Kanarienvogel erweitert** (`test_canary.py`, `tests/_support/canary.py`): `public_responses()` ruft zusätzlich jede neue Route ab (`/events` mit und ohne `q`, `category`, `organization`, `past`, `/events/{slug}` aller Kanarien-Dossiers, `/today`, `/categories`, `/calendar`, `/archive`, `/ics/e/{slug}.ics`, die Hülle auf `/`, `/suche?q=CANARY`, `/kalender`, `/rueckblick`, `/e/{slug}`, `/k/{slug}`, `/sitemap.xml`, `/robots.txt`, dazu 404-, 422-, 429-Antworten) und `leaks()` sucht in Körper **und** Headern nach `CANARY-INTERNAL-`, den Betragsziffern und `FORMAT_ONLY`; die öffentlichen Marker `CANARY-PUBLIC-*` müssen in Liste/Detail/Hülle **vorkommen** (Beweis, dass der Scan Text findet).
3. **Facetten:** feste Fixture (3 Kategorien mit Elternbeziehung, 3 Organisationen, 2 Monate, ein abgesagtes, ein archiviertes, ein Entwurf, ein zurückgezogenes Event): Zähler stimmen, disjunktiv (Wahl einer Kategorie ändert deren Geschwister-Zähler nicht), Entwurf/zurückgezogen nie in Treffern, Facetten oder Sitemap, Elternkategorie zählt Kinder, `facets`/`total` nur auf der ersten Seite.
4. **Suche:** die 20 Mustersuchen (6.4), Tippfehler ("Movienigth"), Kompositum, Akzent ("Cafe"/"Café"), `-`-Ausschluss, Syntaxeingabe; Treffer sind Teilmenge der Feed-Items (`/feed/events`), `past`, `from`/`to`, Cursor-Durchlauf ohne Doppel und Lücken (beide Cursorformen).
5. **Rate-Limit:** mit `rate_limit_enabled` und kleinen Grenzen: das 31. Such-Fehlschlag derselben IP in einer Minute gibt 429 mit `Retry-After`; Treffer aus dem Cache zählen nicht; zwei IPs getrennt; Redis aus = kein Fehler (fail-open).
6. **Cache-Invalidierung** (`test_cache_invalidation.py` erweitert): nach `publish`, `unpublish`, `archive`, `restore`, `cancel`, `postpone`, `reinstate` und Poster-Wechsel liefern `/events`, `/events/{slug}`, `/today`, `/calendar`, `/categories`, `/archive`, die Hülle und die Sitemap **sofort** den neuen Stand (Version-Zähler erhöht); `ETag` ändert sich, `If-None-Match` mit dem alten ETag gibt 200, mit dem neuen 304.
7. **Hülle (Golden):** `tests/golden/shell/event-scheduled.html`, `event-cancelled.html`, `event-no-image.html`, `category.html`, `home.html` -- der erzeugte `<head>`-Block für ein festes Fixture-Event mit festem `index.html`-Fixture (`tests/fixtures/spa-index.html`); Vergleich Byte für Byte, Neuerzeugung nur mit `--update-golden`. Zusätzlich: `og:title`, `og:description`, `og:image` (= `og_1200x630`-URL), `og:url`, `canonical`, `<link rel="alternate" type="text/calendar">`, JSON-LD parsebar (`json.loads` nach Entfernen der Escapes) und gegen das schema.org-Pflichtfeldset (`name`, `startDate`, `location` oder `eventAttendanceMode`) geprüft; `offers` fehlt ohne `ticket_url`; ein Titel `"><script>alert(1)</script>` erscheint nirgends unescaped; identischer Körper für drei User-Agents; 404 mit `noindex`; `Content-Security-Policy` genau einmal; kein `Set-Cookie`.
8. **Cookie-Freiheit:** `GET` auf jede neue Route **und** `GET /api/auth/me` ohne Cookie liefert keinen `Set-Cookie`; `GET /api/auth/me` mit gültiger Session setzt das XSRF-Cookie weiter (Anmelde-Pfad bleibt intakt); der OIDC-Callback setzt Session- **und** XSRF-Cookie.
9. **Sitemap:** enthält jedes öffentliche Event/jede aktive Kategorie genau einmal, keine Entwürfe, wohlgeformt (`xml.etree`), `lastmod` UTC; Kappung bei > 45 000 per Monkeypatch der Grenze; `robots.txt` Wortlaut.
10. **Einzel-ICS:** Golden `tests/golden/ics/event-single.ics` (UID, SEQUENCE, STATUS:CANCELLED für abgesagte), `attachment`-Disposition, 404 für unbekannt/Entwurf, vergangenes Event abrufbar; Schemathesis-Lauf (`test_schemathesis.py`) erweitert um die neuen Routen gegen das aus FastAPI erzeugte OpenAPI; für die Antwortformen der Liste/des Details kommt `tests/schema/public-site-v1.json` als Vertrag dazu (CODEOWNERS-Eintrag wie bei `feed-v2.json`).
11. **Migration `0008`:** `test_migration_0008.py` -- Upgrade auf einer `0007`-Datenbank mit Events in allen Zuständen: View-Zeilenzahl unverändert, `search_tsv` gefüllt, `events_public` kann `search_tsv` lesen, aber nichts aus `event` (`SELECT` auf Tabelle schlägt fehl); Downgrade stellt die View wieder her. `migrations-check` in CI bleibt grün (ein Head).
12. **Performance (5000 synthetische Events):** `scripts/b1_perf.py` (Skript, kein Test im Standardlauf) und ein Integrationstest `test_public_perf.py` (Marker `perf`, in CI optional/nightly, lokal in der Abnahme): legt 5000 `published`/`archived` Events über Organisationen/Kategorien/Titel aus einer festen Wortliste an (Seed fest, deterministisch, über den App-Pfad `seed_dev`-Muster oder direktes Einfügen als Test-Rolle, danach `ANALYZE event`), misst je 200 Anfragen gegen `/api/public/events` (Liste ohne `q`, mit `q`, mit `category`, mit `from`/`to`, Facetten inklusive) und gegen `/api/public/events/{slug}`, `/today`, `/calendar` **ohne Antwort-Cache** (Redis aus oder `flushall` je Anfrage) und fordert **p95 < 300 ms** für Suche und Liste, dazu einen `EXPLAIN (FORMAT JSON)` der Suche, der `ix_event_search_tsv` oder den Trigram-Index nennt. Die Messumgebung (Dev-Postgres, eine API-Instanz) und die Zahlen stehen im Abnahmeprotokoll; verfehlt die Suche die Marke, ist der Teilindex aus 2.1 Punkt 4 der erste Schritt.

### 6.2 Frontend

Jest (`npm test`): Services (URL-Bau, Fehlerabbildung 422/429/404), Modelle, Facetten-Zustand aus URL und zurück, Semester-Gruppierung, Kalender-Adapter, Kopieren/Teilen (mit und ohne `navigator.share`/`clipboard`), Header-Navigation (aktive Seite), Footer-Links, Bottom-Bar (vier Einträge, `aria-current`), Frame-Erzwingung (`frame: 'public'` mit Session), Seiten-Specs je Screen (Ladezustand, Leerzustand, Fehler, abgesagt/verschoben als Text, kein `<img>` ohne `width`/`height`), `ngsw-navigation.spec.ts` mit `!/robots.txt`, `translations.spec.ts` (keine fehlenden Schlüssel), Entfernung von `home.*`.

Playwright (`frontend/e2e/public.spec.ts`, neue Spec, nutzt die Dev-Stacks wie `m5b.spec.ts`; Fixture-Events legt `global-setup.ts`/`support` über die API an: eines mit Poster und Ticket, eines abgesagt, eines vergangen mit Poster, eines in einer Elternkategorie):

1. **Heute -> Detail -> In Kalender:** `/` zeigt Hero und Liste, Klick auf das Event öffnet `/e/<slug>`, der Knopf "In Kalender" löst den Download von `<slug>.ics` aus (`page.waitForEvent('download')`), Inhalt beginnt mit `BEGIN:VCALENDAR` und enthält `SUMMARY:` des Events.
2. **Suche mit Facette:** `/suche`, Eingabe, Treffer erscheinen live (ohne Knopf), Facette "Kategorie" wählen -> URL trägt `category=`, Zähler stimmen, Zurück-Taste stellt den Zustand her, Leerzustand mit "Filter zurücksetzen".
3. **Kalender:** Monat, Tag mit Event, Klick öffnet Liste; Tastatur (Pfeiltasten im Raster); Monatswechsel; Phone: Agenda.
4. **Kategorie-Abo:** `/k/<slug>` -> "Kalender abonnieren" -> `/abos#k=<slug>` zeigt `webcal://…/ics/k/<slug>.ics` und `https://…`; "Kopieren" (`clipboard`-Berechtigung im Test erteilt) legt die URL ab; `GET` der URL liefert `text/calendar`.
5. **Phone-Viewport 390 x 844:** alle Routen (`/`, `/suche`, `/kalender`, `/e/<slug>`, `/k/<slug>`, `/rueckblick`, `/abos`, `/impressum`, `/datenschutz`, `/offline`, 404) ohne horizontales Scrollen; Bottom-Bar sichtbar mit vier Einträgen, Header-Navigation nicht; Touch-Ziele >= 44 px (4.2); Facetten-Sheet öffnet, Fokus bleibt darin, `Esc` schließt.
6. **axe** (`@axe-core/playwright`, Regelsätze wcag2a/aa/21aa) auf allen genannten Routen in **Hell und Dunkel**, 1280 px und 390 x 844: keine Befunde der Stufen `critical` und `serious` (die Abnahme verlangt "ohne kritische Befunde"; der Test ist strenger, `moderate` wird protokolliert).
7. **Netzwerk-Allowlist:** `page.on('request')` sammelt jede URL beim Durchlauf aller Routen; jede muss dieselbe Origin wie `baseURL` haben (`data:`/`blob:` erlaubt); fremde Origin = Fehlschlag; zusätzlich `page.on('response')`: kein `set-cookie`-Header in irgendeiner Antwort der Public-Routen **für einen anonymen Kontext** (`/api/auth/me` eingeschlossen, siehe 2.9), und `context.cookies()` ist am Ende leer.
8. **Angemeldet:** ein angemeldeter Kontext sieht auf `/` die öffentliche Seite (kein Redirect), der Header zeigt "Zum Dossier", der Link führt nach `/dossiers`.
9. **Fehler:** `route.fulfill` mit 429 -> Meldung "Zu viele Anfragen. Bitte warte einen Moment."; Netzwerkabbruch -> Fehlerzustand mit "Neu laden".

Die Specs `m1` bis `m5b` laufen unverändert weiter (nach der Redirect-Änderung 3.1 nachgezogen). Der axe-Lauf gegen den **Produktions-Build hinter nginx** (laut `M5B-ABNAHME.md` Punkt i bisher nicht gelaufen) gehört für die Public-Routen in diese Abnahme: `E2E_BASE_URL=http://127.0.0.1:8081 npx playwright test e2e/public.spec.ts` gegen die Compose-`web`.

### 6.3 Link-Vorschau, Hülle, nginx (`deploy/public-smoke.sh`)

Skript gegen die Compose-`web` (Aufruf: `docker compose -f deploy/docker-compose.yml --env-file deploy/.env.dev up -d --build web`, danach `deploy/public-smoke.sh http://127.0.0.1:8081`, danach wieder `down`):

1. Für ein Fixture-Event mit Poster: `curl` mit den User-Agents `WhatsApp/2.24.1`, `Synapse (bot; +https://github.com/element-hq/synapse)` (Matrix), `facebookexternalhit/1.1` und `Signal-Desktop/7.0`: jede Antwort enthält `og:title`, `og:description`, `og:image` (URL auf `/api/public/media/…-og_1200x630.webp`, die ihrerseits mit `curl` 200 `image/webp` liefert), `og:url`; die vier Körper sind byte-gleich.
2. Header: genau ein `Content-Security-Policy`, kein `Set-Cookie`, `Cache-Control` mit `max-age=60`, `ETag`; ein zweiter Abruf mit `If-None-Match` liefert 304.
3. Hülle und `/index.html` nennen dieselben `main-*.js`/`styles-*.css` (Beweis, dass das API-Image zum `web`-Image passt, 5.2).
4. Log: nach `curl '/suche?q=GEHEIM'` und `curl '/api/public/events?q=GEHEIM'` steht `GEHEIM` in keinem Container-Log (`docker compose logs web api`; hier ist zu prüfen, ob uvicorn die Anfragezeile samt Query loggt: **Builder prüft `logging_config.py`**; tut er es, wird das uvicorn-Accesslog im Compose-Start abgeschaltet oder auf den Pfad gekürzt, denn die Aufgabe nennt nur nginx, der Plan will "keine Suchtexte in Logs").
5. Proxy-Cache: zwei Abrufe von `/api/public/today` innerhalb 60 s erreichen die API einmal (Zähler über das API-Log oder `X-Cache-Status`-Header `add_header X-Cache-Status $upstream_cache_status` nur in der Smoke-Variante).
6. Manuell, einmalig, im Protokoll: Link in Matrix (Element) und WhatsApp (Mobil) und Signal einfügen, Screenshot-Beleg. **Offen und nicht belegt:** ob WhatsApp und Signal ein WebP-`og:image` darstellen (die Plattform erzeugt nur WebP-Derivate, `media/derivatives.py`). Zeigt eines kein Bild, kommt ein zusätzliches JPEG-Derivat für `og:image` in die Ableitung (Änderung in `media/derivatives.py` und der Media-Route, eigener Kleinauftrag), nicht vorab.

### 6.4 Korpus "20 Mustersuchen"

`backend/tests/fixtures/public_search_corpus.yaml`: 20 Einträge `{q, filter, expect: {contains: [slugs], excludes: [slugs]}}` auf einem festen Fixture-Bestand, abgeleitet aus den Beispiel-Events und Kategorien der Karte (`stupa-wp-plugin-phase1/KARTE.md` §2.3/2.7: Movienight, Fachschaftssitzung FSI, STUPA-Sitzung, CaIPi-Night, Karaoke im Rappen, Skiausfahrt, Skydiving, Offenes Präsidium, Culture Chill & Chat, Repair Café, Kart fahren, Campusfest). Pflichtmuster: einzelnes Wort ("Kino"), Teilwort ("Movie" findet Movienight), Tippfehler ("Movienigth", "Karaokke"), Akzent/Umlaut ("Cafe" findet "Café", "Praesidium" findet "Präsidium"), Kompositum, zwei Wörter (UND), Ausschluss ("Sitzung -STUPA"), Anführungszeichen ("Culture Chill"), Kategorie als Wort ("Party"), Ort ("Rappen"), Gebäude, Organisationskürzel ("FSI"), englisch ("movie night"), Zahl ("2026"), zu kurz ("a" -> kein Filter), nichts Auffindbares (leere Liste), Sonderzeichen (`%`, `_`, `'`, `\`) ohne Fehler, Länge 101 (-> 422). Der Lauf prüft jede Suche über HTTP gegen die Integrationsumgebung und im Perf-Test gegen den 5000er-Bestand (dieselben Erwartungen, bei mehr Rauschen nur `contains`).

## 7. Abnahme B1/B2 (Wortlaut aus PLAN §16.2)

> **B1** Öffentliche Shell und Bottom-Bar, Heute (P01), Suche mit Facetten (P02), Kalender (P03), Detail mit HTML-Hülle (P04), Kategorie (P05), Campus heute (P10), Rückblick (P13), Fehlerseiten (P14), Sitemap, robots, Log-Format ohne Query. **Fertig wenn:** Link-Vorschau in Matrix, WhatsApp, Signal zeigt Titel und Poster; 20 Mustersuchen bestehen; 5000 synthetische Events unter 300 ms p95; kein `Set-Cookie`; Netzwerk-Allowlist-E2E (nur eigene Origin) grün; axe ohne kritische Befunde in Hell und Dunkel auf 390×844.
>
> **B2** ICS je Profil, Token-Verwaltung, Abos-Seite (P07). **Fertig wenn:** Token nur als Hash, nie im Log (Test), Rotation invalidiert, unbekannt und widerrufen geben dieselbe 404.

| # | Prüfpunkt | Nachweis | Stand dieses Kontrakts |
|---|---|---|---|
| a | Link-Vorschau in Matrix, WhatsApp, Signal zeigt Titel und Poster | 6.3 Punkt 1 (curl mit den User-Agents) plus manueller Beleg 6.3 Punkt 6 | Titel/Poster-Tags per curl prüfbar; **WhatsApp/Signal-Darstellung eines WebP nicht belegt** (8.7) |
| b | 20 Mustersuchen bestehen | 6.4, Integrationstest `test_public_search_corpus.py` und Perf-Lauf | gedeckt |
| c | 5000 synthetische Events unter 300 ms p95 | 6.1 Punkt 12, Zahlen im Protokoll | gedeckt; Zahl offen bis zum Lauf |
| d | kein `Set-Cookie` | 6.1 Punkt 8, 6.2 Punkt 7, `public-smoke.sh` Punkt 2; Ursache und Lösung 2.9 | gedeckt, setzt die CSRF-Änderung voraus |
| e | Netzwerk-Allowlist-E2E (nur eigene Origin) grün | 6.2 Punkt 7 | gedeckt |
| f | axe ohne kritische Befunde, Hell und Dunkel, 390×844 | 6.2 Punkt 6, auch gegen den Produktions-Build hinter nginx | gedeckt |
| g | Sitemap, robots, Log ohne Query | 6.1 Punkt 9, 6.3 Punkt 4, 5.1 Punkt 3 | gedeckt |
| h | Seiten P01 bis P05, P07 (ohne Profil), P10 (nur heutige Events), P13, P14 vorhanden | 6.2 Punkt 1 bis 5 | gedeckt |
| i | **B2: Token nur als Hash, Rotation, dieselbe 404** | entfällt in diesem Schnitt | **nicht Teil dieser Abnahme**: Profil-ICS und Token-Verwaltung gehören laut Auftrag zu B3 (8.1); die Abos-Seite P07 mit ICS je Kategorie und `all` ist drin (Punkt h) |
| j | Gates | `uv run ruff check .`, `ruff format --check .`, `basedpyright`, `pytest -m 'not integration and not e2e and not live'`, `pytest -m integration`, `PROVENANCE_STRICT=1`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `deploy/compose-lint.sh`, `deploy/smoke.sh`, `deploy/public-smoke.sh`, `alembic heads` (ein Head) | verpflichtend; Protokoll `docs/B1-ABNAHME.md` |

## 8. Abweichungen

1. **Profil-ICS und Token nicht in B2.** PLAN §16.2 führt "ICS je Profil, Token-Verwaltung" unter B2; der Auftrag zieht beides nach B3 (zusammen mit `subscriber`). B2 reduziert sich auf die Abos-Seite P07. Die dritte Abnahmespalte aus 7 (Token-Hash, Rotation, dieselbe 404) wird in den B3-Kontrakt übernommen. Vorgemerkt dort auch PLAN §18 Minor 2 (Antwortzeit bei bekannter/unbekannter Adresse).
2. **Kein 410 auf `/e/{slug}`.** P04 sieht 410 "nicht mehr verfügbar" für Zurückgezogenes vor. `events_public` liest nur `public_event_v`; ein zurückgezogenes und ein nie vorhandenes Event sind dort nicht unterscheidbar, und die Unterscheidung würde Entwürfe preisgeben. Es bleibt bei 404 mit dem Text "gibt es nicht oder nicht mehr verfügbar".
3. **Rate-Limit zählt Cache-Fehlschläge, nicht Treffer** (2.10). Wortlaut des Auftrags: "z. B. 120/min je IP". Grund: Campus-NAT, ein Treffer kostet fast nichts, nginx deckt den billigen Pfad mit `limit_req`. Die Werte sind Einstellungen (`RL_PUBLIC_PER_MINUTE`, `RL_PUBLIC_SEARCH_PER_MINUTE`), ihre Eignung für den echten Datenverkehr ist **nicht gemessen**.
4. **Keine nginx-Ausnahme "nur X-Frame-Options" für die Hülle** (PLAN §8.4). Die Hülle trägt denselben CSP-Wert wie nginx, `api-proxy.conf` versteckt den API-Header, nginx setzt seinen: ein Header je Route, durch `smoke.sh` geprüft.
5. **Bottom-Bar-Plätze** Heute · Suche · Kalender · Abos statt Heute (inkl. Suche) · Kalender · Karte/Campus heute · Abos (PLAN §8.6, §15.2). Auftrag nennt vier Einträge mit Suche; "Campus heute" wird als Abschnitt von P01 geführt, solange es keine Dauerangebote gibt.
6. **Kein QR-Code auf P07** (§15.2 listet `app-qr-code`): die Kit-Komponente und eine Server-Matrix sind nicht gebaut; für B1 reicht Link + Kopieren + `webcal://`. Nachziehbar, kein Blocker.
7. **`/ics/k/<slug>.ics`, nicht `/ics/c/…`** (PLAN §8.3): die gebaute und getestete Route (`ics_router.py`, M5) bleibt, die Abos-Seite zeigt sie so. Umbenennen würde bestehende Abos brechen; es gibt noch keine produktiven, aber der Pfad ist öffentliche Schnittstelle.
8. **Hauptkategorie plus Eltern statt Mehrfachkategorien** für Facetten und Filter (Modell kennt nur `primary_category_id`).
9. **`/archive` nutzt "vorbei" statt `state = 'archived'`**, weil die View keinen Zustand führt (2.7).
10. **Standard-OG-Bild** `og-default.png` ist neu (L18); PLAN nennt nur das Poster-Derivat.
11. **CSRF-Cookie-Regel geändert** (2.9): das XSRF-Cookie kommt nur noch mit Session. Das berührt M1-Verhalten (`middleware.py`); ohne die Änderung bekäme jeder anonyme Besucher durch `/api/auth/me` ein Cookie, und "kein `Set-Cookie`" wäre auf Seitenebene nicht erfüllbar. Annahme: kein Frontend-Pfad braucht das Cookie ohne Session (der Interceptor liest es nur für Schreibzugriffe, `auth.interceptor.ts`); **Builder belegt das mit `m1` bis `m5b` und dem Login-Pfad**.
12. **Pool der Public-Rolle verkleinert** (L13) wegen `CONNECTION LIMIT 8`.
13. **`/` ist für Angemeldete nicht mehr der Sprung ins Dossier** (3.1). Vorgänger-Verhalten laut M1/M5b; Luis hat die öffentliche Startseite als eigenes Ziel bestellt, der Weg ins Dossier ist der Header-Link.

Offene Punkte, die ein Mensch klären muss (nicht von mir entschieden): Produktions-Domain (ENTSCHEIDUNGEN schlägt `events.reutlingen.university` vor, bestätigt ist sie nirgends); Impressum und Datenschutz (Hochschule, DSB); ob der Rückblick Absagen zeigen soll (hier ja, mit Text); Darstellung des WebP-`og:image` in WhatsApp/Signal (6.3 Punkt 6).

## 9. Verzeichnisbesitz

Zwei Builder arbeiten parallel; ein Pfad gehört genau einem. Gemeinsam gelesen, nie gleichzeitig geändert: `docs/` (ein Dokument je Builder), `PROVENANCE.json` (der Integrationsschritt führt beide Einträge zusammen), `.github/workflows/ci.yml` (Integrator).

**Backend-Builder (`backend/**`, `deploy/**`):**
- `backend/app/modules/publicapi/**` (neue Dateien aus Abschnitt 2, `allowlist.py`, `ics_router.py`, `router.py`-Abhängigkeiten, `db.py`)
- `backend/app/main.py` (Router einhängen: `site_router` unter `/api`, `shell.router` und `ics_router` ohne Präfix), `middleware.py`, `shared/errors.py` (2.9), `settings.py`, `.env.example`/`deploy/.env*.example` (neue Einstellungen), `events/postcommit.py` (nur falls die Invalidierung eine Lücke zeigt)
- `backend/migrations/versions/0008_public_site.py`, `backend/app/modules/taxonomy/**` (Feld `description`, Seeds `reference.py`), `backend/app/modules/admin/**` nur soweit die Kategorie-Update-Route das Feld braucht
- `backend/worker/public_cache.py` (Sitemap-Snapshot), `backend/worker/main.py` falls der Job-Name sich ändert (er ändert sich nicht)
- `backend/tests/**`, `backend/scripts/b1_perf.py`, `backend/scripts/b1_acceptance.py`
- `backend/Dockerfile`, `deploy/docker-compose.yml`, `deploy/web/nginx.conf`, `deploy/web/security-headers.conf` (unverändert, nur gelesen), `deploy/compose-lint.sh`, `deploy/smoke.sh`, `deploy/public-smoke.sh`, `deploy/.env.host.example`
- `docs/B1-ABNAHME.md` (Protokoll, Abschnitte Backend/Deploy)

**Frontend-Builder (`frontend/**`):**
- `frontend/src/app/features/public/**`, `layout/public-header/**`, `layout/public-bottom-bar/**`, `layout/site-footer/**`, `layout/shell.component.*` (Rahmen-Erzwingung), `app.routes.ts`, `feature-routes.ts` nur falls nötig
- Löschungen: `pages/home/**`, `core/auth/home-redirect.guard*`, Schlüssel `home.*`
- `shared/event-time.ts` (Umzug aus `features/dossiers/api/event-time.ts` samt Specs und Imports in `dossiers` und `archive`)
- `core/i18n/translations.public.de.ts`, `translations.ts`
- `frontend/ngsw-config.json`, `core/pwa/ngsw-navigation.spec.ts`, `frontend/public/theme-init.js`, `frontend/public/og-default.png`, `frontend/src/index.html` (nur der Skript-Eintrag), `frontend/proxy.conf.json` (`/ics`)
- `frontend/e2e/public.spec.ts`, `e2e/support/**` für die Public-Fixtures, `e2e/README.md`, Anpassungen in `m1` bis `m5b` falls der Redirect sie berührt
- Admin-Formular I23 (Feld `description` der Kategorie): `features/admin/taxonomy/**`, `translations.admin.de.ts` -- Frontend-Builder, die Route ist Sache des Backends
- `docs/B1-ABNAHME.md` (Abschnitte Frontend/E2E)

**Schnittstellen zwischen beiden (der Vertrag ist dieses Dokument, 2.2 bis 2.8):** Pfade, Parameternamen, Feldnamen (camelCase), Fehlercodes (`invalid_query`, `query_too_long`, `invalid_cursor`, `rate_limited`, `search_unavailable`, `spa_not_built`, `not_found`) und die wurzelrelativen URLs. Das Frontend hält die Typen in `public.models.ts`, das Backend `tests/schema/public-site-v1.json`; weichen beide ab, gewinnt dieses Dokument, und der Builder, der abweicht, ändert es per eigenem Commit mit Begründung.

**Integrationsschritt (Reihenfolge):** Branch `feat/b1-public` von `feat/m5b-vereinfachung`; Backend-Builder zuerst (Migration, API, Hülle), Frontend-Builder gegen die laufende API (`deploy/dev-up.sh`); dann Compose-`web`-Lauf (`up -d --build web`, `public-smoke.sh`, Playwright gegen :8081, danach `down`); `docs/B1-ABNAHME.md`; kein Push, kein Deploy ohne Okay von Luis.
