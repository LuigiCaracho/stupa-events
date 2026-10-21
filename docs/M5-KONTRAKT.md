# M5-Kontrakt: Archiv, Vorlage, Feed und ICS

Verbindlich für die drei Builder von M5 (**backend-archiv**, **backend-public**, **frontend**). Quellen: `PLAN.md` §3.3 (`format`, `event.outcome`, `facts`, `document`), §3.4, §3.5, §4.3 (T08, T08b, T09, T09b, T10) und §4.4, §4.6, §5.4, §7.3, §7.4, §7.7, §8.1 bis §8.3, §15.1 (I06, I18, I19, I20, interner Kalender), §16.1 (Zeile M5 und Meilenstein A-I), §18 (Minor 2, 3, 4), Entscheidungslog E03, E10, E11, E12, E13, E14, E15, E26, E39, E41, E42 samt Nachträgen A05, A06, A07, A08, A13, `ENTSCHEIDUNGEN.md`, `docs/M1-KONTRAKT.md` bis `docs/M4-KONTRAKT.md` (gelten weiter, ihre Abweichungslisten ebenso), `docs/M4-ABNAHME.md` Abschnitt "Offen", `CLAUDE.md`, die Skills unter `.claude/skills/*`, Vorarbeiten `stupa-wp-plugin-phase1/phase2/ENTWURF.md` §11 (Feed-Schema, deutsche Feldnamen; die Plattform nutzt die englischen Schlüssel aus M1) und `stupa-wp-plugin-phase1/KARTE.md` §2.7 und §3.3, Upstream `STUPA-Workflow@93c33d6` (U, read-only) für Muster (`U backend/app/modules/calendar/ics.py`, `U backend/app/search.py`, `U backend/app/modules/search/{router,service}.py`, Frontend-Beschreibung in `lesen/wf-frontend.md`: Kalender-Monatsraster `features/meetings/meetings-calendar`, `CommandPaletteComponent`). Pfade `U ...` sind relativ zu `upstream/STUPA-Workflow`.

Stand der Analyse: Branch `feat/m4-dossier` (HEAD `9623ad8`, M4 committet), Arbeitsbaum ohne M5-Änderungen, Migrationen bis `0005_dossier_knowledge`, Dev-Stack (`deploy/docker-compose.dev.yml`) läuft und stand für die Messungen in 6.2 zur Verfügung (nur `SELECT` und `TEMP TABLE` in einer zurückgerollten Transaktion). Der Branch `feat/m5-archiv` entsteht erst im letzten Schritt (nach Review); bis dahin kein Commit, kein Push. Wo dieser Kontrakt dem PLAN oder M1 bis M4 widerspricht, gewinnt der Kontrakt, die Abweichung steht in Abschnitt 13. Was nicht belegt ist, steht als Vorschlag in 13.2 und wartet auf Luis; die **fett** markierte Voreinstellung gilt, bis er anders entscheidet. Kein Live-System wird berührt (kein Aufruf von `stupa.reutlingen.university`, `workflow.*`, `sso.*`).

## 1. Lückenanalyse

Jede Zeile ist gegen den Code geprüft (Datei in Klammern), nicht gegen die Kontrakte.

### 1.1 Was schon existiert

| Teil | Stand | Beleg |
|---|---|---|
| Zustandsmaschine mit T08, T08b, T09, T09b, T10 als Daten; `due_transition` (Ende + 12 h, 30 Tage `followup`); Worker `advance_states` feuert T05, T08, T08b, T09b über `stage_system_fire` (alle Guards laufen) | vorhanden | `pipeline/transitions.py`, `pipeline/advance.py`, `worker/advance.py` |
| Nachbereitungs-Guards `retrospectiveFilled`, `outcomeSetOrWaived`, `howtoVerified` als getestete reine Funktionen mit Codes `retrospective_missing`, `outcome_missing`, `howto_unverified`; im `Snapshot` mit Standard `True`; `checklist_done` liest immer die Phase `planning` | Platzhalter, Datenquelle fehlt | `pipeline/guards/content.py`, `pipeline/snapshot.py`, `dossier/guard_data.py` (`phase="planning"`) |
| `document` mit `carry_over`, `verified_at/_by`, `kind` inkl. `retrospective` im CHECK, Revisionen, Autosave-Entwurf, Diff; `event_id NOT NULL` | vorhanden (M4), aber nur Besitzer Dossier | `0005_dossier_knowledge`, `dossier/models_documents.py` |
| `checklist_template`, `checklist_template_item`, `checklist_item` mit `due_offset_days`, `due_manual`, `recompute_due`, `apply-template` | vorhanden | `dossier/checklist.py`, `dossier/checklist_due.py`, `0005` |
| Notifications: `notify`, `dispatch_mails`, sieben Kinds, `dedupe_key UNIQUE`, Cron-Muster `send_due_reminders` | vorhanden | `notifications/kinds.py`, `worker/mail.py` |
| Feed `GET /api/public/feed/events` live aus `public_event_v` über die Rolle `events_public`; `ETag` als Hash der Items, 304, Filter `from, to, category, org, limit`; `FeedOut` mit `items[]`; Medienroute; `invalidate_feed_cache` zählt nur `events:feed:version` hoch (kein Leser) | vorhanden (M1/M3) | `publicapi/{router,service,schemas,db}.py`, `pipeline/actions.py`, `tests/schema/feed-v2.json` |
| View `public_event_v` (M3-Fassung): Hauptkategorie, `venue_text` (private Orte als `NULL`, freier Ortstext **immer** öffentlich), Poster-Derivate, `public_reason_*`; Zeilen in `live, followup, archived` mit gültigem Poster oder Ausnahme | vorhanden | `0004_pipeline_full` (`_VIEW_M3`) |
| CHECK gegen Steuerzeichen und U+2028/2029 auf `event.title, summary, venue_text, cost_text, public_reason_text, ticket_url, website_url` und `venue.name, address, notes` | vorhanden | `events/models.py` (`CONTROL_CHARS`), `taxonomy/models.py` |
| Textsuche-Konfiguration `de_unaccent`, `immutable_unaccent`, Erweiterungen `pg_trgm`, `unaccent`; Helfer `fts_rank`, `trigram_rank`, `escape_like` | Gerüst; `fts_rank` und `trigram_rank` haben nur Testaufrufer, kein `tsvector`, kein Index, kein Router | `0001_baseline`, `shared/search.py`, `tests/unit/shared/test_misc.py` |
| `GET /api/events` mit `view=list|board`, Filter (`state, organization, category, mine, q (ILIKE), from, to`), `Page`; Sichtbarkeit `readable_org_ids`/`visible_events_query`; `load_visible` verbirgt Dossiers fremder Organisationen mit 404 | vorhanden | `events/{router,listing,access}.py`, `orgs/scope.py` |
| `attachment_readable` bildet die Sichtbarkeitstabelle (PLAN 5.4) inklusive `shared` vollständig ab; Zugriff auf fremde `shared`-Anhänge archivierter Dossiers ist unerreichbar, weil `load_visible` vorher 404 gibt (M4 10.1.8) | vorhanden, Lesepfad fehlt | `files/access.py` |
| Rechte `library.read` (alle Rollen), `library.manage`, `format.manage` (nur `editor`), `event.submit`, `event.restore`, `event.cancel` | vorhanden, reichen für M5 (**kein neues Recht**) | `shared/permissions.py` |
| Aktion `confirm-flyer` unter `/api/events/{id}/actions/...` als Muster für weitere Bestätigungsaktionen | vorhanden | `pipeline/actions_router.py` |
| nginx-Locations `/ics/` und `/ics/p/` (Ratenbegrenzung, Body 1 KB), Log-Format `ev_noquery` nur für `/api/public/`; kein ICS-Router in der App | Gerüst | `deploy/web/nginx.conf` |
| Worker-Registry und Cron (`advance_states`, `send_due_reminders`, `gc_*`); Backup mit Zeilenzahl-Manifest über **alle** Tabellen; `deploy/restore-smoke.sh` | vorhanden; **kein CI-Job** `restore-smoke` | `worker/main.py`, `deploy/backup.sh`, `deploy/restore-smoke.sh`, `.github/workflows/ci.yml` |
| Frontend: Dossier-Reiter (Übersicht, Anhänge, Anleitung, Checkliste, Mails, Verlauf), `app-list-detail`, `app-list-item`, `app-search-pill`, `app-filter-select`, `app-markdown-diff`, `dossier-markdown-editor` (Textarea ist Standard, Gate nicht bestanden), Nav mit vier Einträgen | vorhanden; **kein** Kalender, keine Palette, keine Routen für Archiv, Formate, Bibliothek | `frontend/src/app/{feature-routes.ts,layout/nav.service.ts,features/dossiers/**,shared/ui/**}` |
| Dev-Werkzeuge: `schemathesis==4.30.1`, `hypothesis`, `jsonschema_rs`, `testcontainers`, Harness `Api` (`tests/integration/events/harness.py`), Abnahmeskript-Muster `scripts/m4_acceptance.py` | vorhanden; Schemathesis wird noch nirgends benutzt | `pyproject.toml`, `tests/` |

### 1.2 Was fehlt

| # | Lücke | Wirkung | Abschnitt |
|---|---|---|---|
| N1 | Kein `format`, kein `event.format_id`, keine Master-Anleitung; `document.event_id NOT NULL` | I18, E10, "Letztes Mal" über Ausgaben nicht baubar | 2.1, 2.3, 4 |
| N2 | Keine Nachbereitungsdaten: `outcome`, Anleitung-geprüft-Marke fehlen; Rückblick hat keine Quelle; `checklistDone(followup)` nicht verdrahtet | T09 zu locker, T09b ohne Kennzeichen | 2.2, 3 |
| N3 | Kein Klonen (`derived_from_id`), kein Lesepfad auf archivierte Dossiers anderer Organisationen | I06, E11, PLAN 5.4 Zeile "archiviert" | 2.2, 4, 5 |
| N4 | Keine interne Suche: weder `tsvector` noch GIN- oder Trigramm-Index noch Router | I20, Vorlagen-Suche | 2.4, 6 |
| N5 | Kein Kalender-Endpunkt, kein `app-calendar-grid` (M3 12.9) | interner Kalender | 7 |
| N6 | Feed Schema 2 unvollständig: kein `since`, kein Cursor, kein `format`, `venue{}`, `sequence`, `updatedAt`, Elternkategorie, `textHtml`; **kein** Worker-Cache; `allDay=true` wird mit 422 abgelehnt (M1); freier `venue_text` ist öffentlich ohne Bestätigung (M1-Abweichung 4, A06) | Feed und ICS nicht pilotfähig, Datenschutzlücke | 2.2, 2.6, 9 |
| N7 | ICS fehlt vollständig; Middleware (`/api/public/`-Präfix für Cookie und `X-Robots-Tag`) und Routeninventur kennen `/ics/` nicht | Abo nach Kategorie | 8 |
| N8 | Kanarienvogel-Test und Allowlist-Lint fehlen; der vorhandene Lint prüft nur `model_dump` im Wurzelverzeichnis von `publicapi` (`glob`, nicht `rglob`); Schemathesis ungenutzt | E39 | 10 |
| N9 | CHECK gegen Steuerzeichen fehlt auf `organization.name/short`, `category.name/short`, `venue.city/postcode`; diese Texte landen in Feed und ICS (A07) | Zeileninjektion über Taxonomie | 2.5 |
| N10 | `event.facts` existiert nicht (Snapshot-Platzhalter `facts_error`), `location_precision` und der Guard `location_unconfirmed` sind Platzhalter (M1-Abweichung 4, M3 12.18, M4 "Offen") | Pilot: Privatadresse im Feed möglich | 2.2, 3.6 |
| N11 | CI-Job `restore-smoke` fehlt (E26: Pflicht vor jedem Release-Tag ab `v0.1.0`); Coverage-Gate steht auf 90 % statt 97 % (Zusage in M2/M3) | Meilenstein A-I | 12, 12.4 |
| N12 | Nav, Bottom-Bar und Routen kennen weder Kalender, Archiv, Formate noch Bibliothek; keine Strg/Cmd+K-Palette | I19, I20 | 11 |

### 1.3 Was M5 nicht liefert

Importe, Dubletten, `legacy`-Bestand und `public_archive` (M6; die View filtert `legacy` deshalb noch nicht), Serien und Dauerangebote (M7; Serien-Termine kommen erst dann als einzelne VEVENTs aus einer Serie), Statusseite und Audit-Ansicht (M8), öffentliche Seiten P01 bis P14, Suche mit Facetten für Anonyme, Profil-ICS (`/ics/p/<token>.ics`), Abos und Newsletter (alles Stufe B), Karten und Koordinaten (Stufe C: weder `lat/lon` noch `geo_override` noch ICS-`GEO`), MCP (D), Bibliotheksverwaltung mit eigenen Dokumenten (`library.manage`, Abweichung 13.1.3), Format-eigene Checklisten und Mailvorlagen (13.1.3), Mitveranstalter (`event_organization`, 13.2 D12).

## 2. Datenmodell-Delta (Migration `0006_archive_feed`)

Genau ein Head `0006_archive_feed` (17 Zeichen), auf `0005_dossier_knowledge`. Frische DB und M4-Upgrade ergeben dieselben Zeilen (`test_migrations`, mit Bestandszeilen aus allen Zuständen). `models.py` wird mitgeführt. Alle Zeitspalten `timestamptz`. JSON-Spalten tragen camelCase-Schlüssel wie `attachment.meta` (M4 2.1); API und Datenbank sprechen dieselben Namen (Abweichung 13.1.4). Datenschritte stehen vor den neuen CHECKs. Das Migrations-Skript schreibt **backend-archiv**; die View in 2.6 und die CHECKs in 2.5 stehen hier wörtlich und gelten als Vorgabe von **backend-public**.

### 2.1 `format` (neu)

`id uuid pk`, `slug text NOT NULL UNIQUE` (CHECK `~ '^[a-z0-9][a-z0-9-]{0,59}$'`), `title text NOT NULL` (1 bis 120, ohne Steuerzeichen), `organization_id uuid NOT NULL` (FK `organization.id` `RESTRICT`), `master_howto_document_id uuid` (FK `document.id` `RESTRICT`, per `ALTER TABLE` nach dem Anlegen von `document.format_id` gesetzt, weil beide Tabellen aufeinander zeigen), `last_verified_at timestamptz`, `last_verified_by text`, `defaults jsonb NOT NULL DEFAULT '{}'` (CHECK Objekt), `description_md text` (<= 20 000 Zeichen), `active boolean NOT NULL DEFAULT true`, `created_by text`, `created_at`, `updated_at`; `search_tsv` siehe 2.4. Indizes `ix_format_organization_id`. Formate werden nie gelöscht (`events_app` ohne `DELETE`, `test_db_grants`), nur `active = false`.

`defaults` (Pydantic, `extra=forbid`): `{categoryId?: uuid, venueId?: uuid, durationMinutes?: int 15..10080, checklistProfile?: generic|party|meeting|trip}`; der Service prüft, dass Kategorie und Ort existieren und aktiv sind. Der Auftrag nennt "Kategorie, Ort, Dauer, Checklisten-Profil"; PLAN 3.3 kennt statt `defaults` die Spalten `default_category_ids` und `default_checklist_template_id` (Abweichung 13.1.5). Die Standard-Checkliste eines Formats ist die Vorlage seines Profils (M4 2.4); eine format-eigene Checkliste gibt es in M5 nicht.

Seeds (`backend/seeds/formats.yaml`, idempotent über `slug`, auch im Test-Harness): `movienight` (Organisation `fsi`, Kategorie `kino`, 180 Minuten, Profil `generic`), `offenes-praesidium`, `fsi-lan-party`, `fsi-game-together`, `caipi-night`, `campusfest`, `skiausfahrt` (PLAN 3.3 nennt diese Beispiele; die Organisation je Format ist **Startvorschlag**, Luis oder die Redaktion prüfen sie, 13.2 D4). Die Organisation der Movienight ist in `KARTE.md` nicht belegt; der Dev-Seed (`seeds/dev_events.yaml`) führt sie unter `fsi`, die Fixture folgt dem.

### 2.2 `event` (Änderung)

| Spalte | Regel |
|---|---|
| `format_id uuid` | FK `format.id` `RESTRICT`, Index; setzt Klon (erbt vom Original), "Als Format speichern" (4.5) und `PUT /events/{id}/format` |
| `derived_from_id uuid` | FK `event.id` `RESTRICT`, CHECK `derived_from_id <> id`, Index; setzt nur der Klon, danach unveränderlich |
| `outcome jsonb` | NULL oder Objekt `{attendance, costsCents, revenueCents, notes, waived, waivedReason}` (3.5); der CHECK prüft nur `jsonb_typeof = 'object'`, die Form prüft die API |
| `howto_verified_at timestamptz`, `howto_verified_by text` | gesetzt von der Aktion `verify-howto` (3.2) |
| `facts jsonb NOT NULL DEFAULT '{}'` | Profil der Hauptkategorie (PLAN 3.4, 3.6) |
| `location_precision text NOT NULL DEFAULT 'hidden'` | CHECK `exact, building, hidden`; gilt für freien `venue_text` (A06) |
| `location_confirmed_at timestamptz`, `location_confirmed_by text` | gesetzt von der Aktion `confirm-location` (3.6) |
| `search_tsv tsvector` | **generiert**, siehe 2.4 |

Es gibt **keine** Spalte `retrospective_md`: der Rückblick ist ein Dokument der Art `retrospective` (3.5, Abweichung 13.1.3). `series_id`, `geo_override`, `lat/lon`, `public_archive`, `owner_id` kommen mit M6, M7, C.

**Bestandsdaten (Datenschritt):** `UPDATE event SET location_precision = 'building', location_confirmed_at = now(), location_confirmed_by = 'system:migration-0006' WHERE venue_id IS NULL AND venue_text IS NOT NULL AND state IN ('live', 'followup', 'archived')`. Sonst verschwände der Ort aller schon öffentlichen Dossiers schlagartig aus dem Feed (Voreinstellung D1, 13.2). Dossiers in `planning`, `in_review` und `approved` bekommen die Bestätigung durch die prüfende Person (3.6).

**Ganztägige Termine:** `all_day`, `starts_on`, `ends_on` und ihr CHECK existieren seit `0002`; M5 hebt nur die API-Sperre `NoAllDay` auf (`events/schemas.py`, M1 3.3 "kommt mit M5"). `allDay: true` verlangt `startsOn` (Datum) und optional `endsOn` (letzter Tag, einschließlich, Standard `startsOn`); `startsAt`/`endsAt` entfallen im Body und werden gesetzt: `starts_at` = 00:00 Ortszeit von `startsOn`, `ends_at` = 00:00 Ortszeit von `endsOn + 1 Tag` (halboffen, Tage mit 23 oder 25 Stunden sind dadurch richtig). `tzid` bleibt `Europe/Berlin`. `wall_clock_ok` und `end_estimated` gelten für ganztägige Termine nicht. Ein Wechsel `allDay` setzt die Spalten `starts_on/ends_on` in derselben Transaktion; `events/writer.update_event` ist die einzige Schreibstelle.

### 2.3 `document` (Änderung)

- `event_id` wird nullable; neu `format_id uuid` (FK `format.id` `RESTRICT`). CHECK `ck_document_owner`: `num_nonnulls(event_id, format_id) = 1`. CHECK `ck_document_format_howto`: `format_id IS NULL OR kind = 'howto'` (Format-Besitz nur für die Master-Anleitung, Abweichung 13.1.3). Partieller Unique-Index `uq_document_format_howto` auf `(format_id) WHERE kind = 'howto'`.
- Partieller Unique-Index `uq_document_event_retrospective` auf `(event_id) WHERE kind = 'retrospective'`; Standard `visibility = 'org'`, `carry_over = false` (M4 2.2).
- `format.master_howto_document_id` zeigt auf die Zeile mit `format_id = format.id AND kind = 'howto'`; der Service hält beides in einer Transaktion gleich.
- `document_revision` bleibt unverändert (append-only). `editor_draft.owner_kind` bleibt `event | document` (Master-Anleitung und Rückblick sind Dokumente).
- `media_ref.owner_type = 'document'` gilt auch für Format-Dokumente; `gc_media` bleibt richtig, weil die Verweise am Dokument hängen.

### 2.4 Volltext und Trigramm

Konfiguration `de_unaccent` (Abbildung `unaccent` vor `german_stem`) existiert seit `0001`. Gemessen auf dem Dev-Stack (PostgreSQL 16.15, `pg_trgm 1.6`): eine **generierte** Spalte mit `to_tsvector('de_unaccent'::regconfig, …)` ist erlaubt, das Gewicht über `setweight` ebenso.

| Tabelle | Spalte `search_tsv` (`GENERATED ALWAYS AS … STORED`) | Indizes |
|---|---|---|
| `event` | `setweight(to_tsvector('de_unaccent', coalesce(title, '')), 'A') \|\| setweight(… coalesce(summary, '') …, 'B') \|\| setweight(… coalesce(description_md, '') …, 'C')` | GIN `ix_event_search_tsv`; GIN `ix_event_title_trgm` auf `immutable_unaccent(title) gin_trgm_ops` |
| `document` | `setweight(… title …, 'B') \|\| setweight(… body_md …, 'C')` | GIN `ix_document_search_tsv`; GIN `ix_document_title_trgm` wie oben |
| `format` | `setweight(… title …, 'A') \|\| setweight(… coalesce(description_md, '') …, 'C')` | GIN `ix_format_search_tsv`; GIN `ix_format_title_trgm` |

Organisations-, Kategorie- und Ortsnamen (PLAN 7.7 Gewicht B) stehen **nicht** im `tsvector` des Dossiers, weil eine generierte Spalte keine Joins kennt; die Suche ordnet sie über Facetten und über einen Trigramm-Zusatz im Abfrage-SQL zu (6.2). Der Dokumenttext gehört als Gewicht D zum Dossier-Treffer, indem die Abfrage passende lesbare Dokumente des Dossiers mitzählt (6.2), nicht über eine Spalte. Indexnutzung des Trigramms: Operatoren `<%` und `%>` mit `SET LOCAL pg_trgm.word_similarity_threshold`; die Funktionsform `word_similarity(…) > x` ist funktional gleich, nutzt den Index aber nicht (bei den erwarteten Größen, einige Tausend Zeilen, trotzdem unter dem `statement_timeout` von 2 s).

### 2.5 CHECKs gegen Zeileninjektion (A07)

Datenschritt je Spalte (`regexp_replace(spalte, '<CONTROL_CHARS>', ' ', 'g')`), dann CHECK mit dem Ausdruck `CONTROL_CHARS` aus `events/models.py`: `organization.name`, `organization.short`, `category.name`, `category.short`, `venue.city`, `venue.postcode`, `format.title`, `format.slug` (nur Muster). Die Pydantic-Modelle der Taxonomie-Verwaltung (`admin/schemas.py`) lehnen dieselben Zeichen mit 422 ab. Bestehende CHECKs (Tabelle 1.1, Zeile "CHECK gegen Steuerzeichen") bleiben. `public_reason_text` ist bereits geschützt. Der ICS-Schreiber entfernt Steuerzeichen **zusätzlich** (8.4); die Datenbank ist das erste, der Schreiber das zweite Netz.

### 2.6 `public_event_v` (Änderung, `CREATE OR REPLACE`)

PostgreSQL erlaubt bei `CREATE OR REPLACE VIEW` nur angehängte Spalten mit unveränderten Namen und Typen. Die Spaltenfolge von `0004` bleibt, neue Spalten stehen am Ende; `GRANT SELECT … TO events_public` überlebt das Ersetzen. Das ist die einzige Stelle, an der die öffentliche Rolle Spalten dazubekommt, und sie ist die Allowlist der Datenbank (E14):

```sql
CREATE OR REPLACE VIEW public_event_v AS
SELECT e.id, e.slug, e.title, e.summary, e.starts_at, e.ends_at, e.all_day, e.tzid, e.public_status,
       o.id AS organization_id, o.slug AS organization_slug, o.name AS organization_name, o.short AS organization_short,
       CASE WHEN e.venue_id IS NOT NULL THEN CASE WHEN v.is_private THEN NULL ELSE v.name END
            WHEN e.location_precision <> 'hidden' THEN e.venue_text END AS venue_text,
       c.slug AS category_slug, c.name AS category_name, c.kind AS category_kind,
       a.sha256 AS hero_sha, a.derivatives AS hero_derivatives, a.alt_text AS hero_alt, a.credit AS hero_credit,
       e.updated_at, e.public_reason_code, e.public_reason_text,
       e.starts_on, e.ends_on, e.public_seq,
       p.slug AS category_parent_slug, p.name AS category_parent_name, p.kind AS category_parent_kind,
       f.slug AS format_slug, f.title AS format_title,
       CASE WHEN e.venue_id IS NOT NULL THEN CASE WHEN v.is_private THEN 'Treffpunkt auf Anfrage' ELSE v.name END
            WHEN e.location_precision <> 'hidden' THEN e.venue_text END AS venue_name,
       CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.public_precision = 'exact' THEN v.address END AS venue_address,
       CASE WHEN v.id IS NOT NULL AND NOT v.is_private AND v.public_precision IN ('exact', 'building') THEN v.city END AS venue_city,
       e.ticket_url, e.website_url, e.cost_text, e.description_md
FROM event e
JOIN organization o ON o.id = e.organization_id
LEFT JOIN category c ON c.id = e.primary_category_id
LEFT JOIN category p ON p.id = c.parent_id
LEFT JOIN format f ON f.id = e.format_id
LEFT JOIN venue v ON v.id = e.venue_id
LEFT JOIN attachment a ON a.id = e.hero_attachment_id AND a.event_id = e.id AND attachment_poster_ok(a)
WHERE e.state IN ('live', 'followup', 'archived') AND e.slug IS NOT NULL
  AND (a.id IS NOT NULL OR exception_ok(e.image_exception))
```

Regeln: (1) `venue_text` bleibt das Feld der M3-Fassung (`NULL` für private Orte), nur der freie Ortstext hängt jetzt an `location_precision`. (2) Private Orte erscheinen ausschließlich als `venue_name = 'Treffpunkt auf Anfrage'` ohne Adresse und Stadt (Auftrag: "nur Name"). (3) Adresse nur bei `public_precision = 'exact'`, Stadt bei `exact` und `building`; die Seeds stehen auf `hidden` (`taxonomy/models.py`), die Adresse bleibt also leer, bis die Redaktion die Genauigkeit eines Ortes anhebt. (4) Der Schema-A-Baum ist zwei Ebenen tief (Fachschaft 138 mit 173, 174, 175); der Join auf **eine** Elternebene reicht, ein Test (`test_category_depth`) stellt sicher, dass kein Seed tiefer geht. (5) Nichts aus `outcome`, `facts`, Kommentaren, Dokumenten, Angeboten, Notizen oder Revisionen steht in der View (`test_public_view_columns` vergleicht die Spaltenliste mit `PUBLIC_EVENT_V` in `publicapi/service.py` und der Allowlist aus 10.3).

### 2.7 Rechte, Trigger, keine weiteren Tabellen

`deploy/db/roles.sql` (Stufe 2): kein `DELETE` auf `format` (`test_db_grants` wächst um `format`, `document` bleibt wie M4); `events_public` bekommt nichts außer `SELECT` auf Views, die Schleife über `public\_%\_v` deckt die geänderte View ab. Der Cache für Feed und ICS ist **keine Tabelle**, sondern Redis (9.5); es gibt kein `public_cache` in der Datenbank. Die Append-only-Trigger von `document_revision`, `event_revision`, `event_status_event` bleiben unverändert. `audit/actions.py` bekommt `EVENT_CLONE`, `FORMAT_CREATE`, `FORMAT_UPDATE`, `EVENT_OUTCOME`, `EVENT_HOWTO_VERIFY`, `EVENT_LOCATION_CONFIRM` (nur IDs im Audit, nie Beträge oder Texte).

## 3. Nachbereitung: T08, T08b, T09, T09b, T10

Die Zustandsmaschine bleibt Daten in `pipeline/transitions.py`; `PipelineService.fire` bleibt der einzige Schreibweg auf `state`. M5 macht die Platzhalter-Guards echt und ergänzt Marken, Mails und die Eingabe der Ergebnisse. Der Vollmatrix-Test bleibt gültig und wächst um die Spalten dieses Abschnitts.

| Id | Änderung in M5 |
|---|---|
| T08 | Regel unverändert (System, Ende + 12 h, `origin_kind` `internal` oder `mcp`). Neu: Erinnerung nach 7 Tagen (3.3) |
| T08b | Regel unverändert (`imported`, `legacy`). Getestet mit `origin_kind` aus der Fabrik; echte Importe kommen mit M6. Kein Rückblick, keine Zahlen, keine Prüfung verlangt |
| T09 | Wer: `event.submit` (Or, Ap, Ed), unverändert. Guards echt (3.1). `format.last_verified_at` in derselben Transaktion (3.2) |
| T09b | Regel unverändert (System, 30 Tage in `followup`). Neu: Kennzeichen "Anleitung ungeprüft" und Mail `auto_archived` (3.3) |
| T10 | unverändert (`event.restore`, Pflichtgrund). Der Eintritt in `followup` zählt neu (`event_status_event`); `outcome`, Rückblick und `howto_verified_*` bleiben stehen |

### 3.1 Guards von T09 (Datenquelle statt Platzhalter)

| Guard (Code) | Quelle und Regel |
|---|---|
| `checklistDone(followup)` (`checklist_open`) | `Transition` bekommt das Feld `checklist_phase: str = "planning"`; T09 setzt `"followup"`. `guard_snapshot`/`load_guard_data` nehmen die Phase als Parameter (`dossier/guard_data.py` kennt ihn schon), `Reason.field` trägt die Phase, die Meldung nennt sie. T02 bleibt bei `planning` |
| `retrospectiveFilled` (`retrospective_missing`) | `Snapshot.retrospective_filled` = es gibt ein Dokument `kind = 'retrospective'` des Dossiers mit `btrim(body_md) <> ''` (Voreinstellung D6: nicht leer). Knopf `fill_retrospective` |
| `outcomeSetOrWaived` (`outcome_missing`) | `Snapshot.outcome_set` = `outcome.waived = true` mit `waivedReason` (>= 10 Zeichen) **oder** `attendance` und `costsCents` gesetzt (0 ist ein gültiger Wert, Voreinstellung D4). Knopf `fill_outcome` |
| `howtoVerified` (`howto_unverified`) | `Snapshot.howto_verified` = `howto_verified_at IS NOT NULL` **oder** es gibt nichts zu prüfen: weder ein Dossier-Dokument `kind = 'howto'` noch ein `format.master_howto_document_id` (Voreinstellung D5). Knopf `verify_howto` |

`FixAction` wird additiv um `fill_retrospective, fill_outcome, verify_howto, confirm_location` erweitert (`pipeline/reasons.py`); die Frontend-Zuordnung zu Knöpfen wächst mit (`guard-list`). Die Reihenfolge der `reasons[]` ist `checklist_open, retrospective_missing, outcome_missing, howto_unverified`. Platzhalter-Standardwerte im `Snapshot` bleiben nur für Unit-Fixturen; **jeder Produktionsweg** liefert echte Werte (Test `test_snapshot_builders_set_m5_fields`, Muster `test_snapshot_builders_set_m4_fields`).

### 3.2 Anleitung prüfen und `format.last_verified_at`

- `POST /api/events/{id}/actions/verify-howto` (Recht `event.submit` in der Organisation des Dossiers; Zustände `live` nach dem Ende, `followup`, `archived`; Body leer): setzt `event.howto_verified_at/_by`; hat das Dossier ein `howto`-Dokument, setzt es dessen `verified_at/_by` in derselben Transaktion. Idempotent (200, kein neuer Zeitstempel). Schreibt eine Revision der Klasse `dossier` und einen Audit-Eintrag. `DELETE` derselben Route hebt die Prüfung auf (nur solange der Zustand nicht `archived` ist).
- **T09** setzt in derselben Transaktion (Hook `after_stage` in `PipelineService.stage_fire`, nur für T09 durch einen Menschen): hat das Dossier ein `format_id`, dann `format.last_verified_at = now`, `last_verified_by = actor.sub` und `verified_at/_by` der Master-Anleitung. PLAN 4.3 nennt das "nach dem Commit"; in derselben Transaktion kann es nicht still ausfallen, weil Aktionen nach dem Commit Fehler nur loggen (13.1.6).
- **`archived` und nachträgliches Prüfen:** `verify-howto` ist in `archived` erlaubt (es ändert keinen Inhalt, nur die Marke), berührt dann auch das Format (kein T09 mehr, der es täte) und nimmt dem Dossier das Kennzeichen "Anleitung ungeprüft". T09b berührt das Format **nie**.
- **Marke "Anleitung ungeprüft":** abgeleitet, nicht gespeichert: `state = 'archived' AND howto_verified_at IS NULL AND (Dossier-Howto oder Master-Howto vorhanden)`. Sie erscheint als farbiger Text (`app-status-text`, Warnfarbe) in Karten (`EventCard.howtoUnverified`), Vorlagen-Treffern (I06), Archiv-Treffern (I20), Ausgabenliste (I18) und im Dossierkopf. "Warnung: Anleitung seit über 12 Monaten ungeprüft" (PLAN 7.3) ist `format.last_verified_at IS NULL OR < now - 12 Monate` und steht als `howtoStale` in `FormatOut`.

### 3.3 Erinnerung und Mail bei T09b

Zwei neue Kinds in `notifications/kinds.py` (Katalog wächst auf neun; der Account-Bildschirm I27 listet sie automatisch, `PrefOut.mailAvailable` steuert den Mail-Schalter):

| Kind | Auslöser | Empfang | Kanal | abschaltbar |
|---|---|---|---|---|
| `followup_reminder` | Worker `send_followup_reminders`: Dossier in `followup`, Eintritt >= 7 Tage her | `created_by`, `submitted_by`, `organizer` der Organisation, nie der `system:`-Akteur | In-App + Mail | ja |
| `auto_archived` | T09b (Mail aus `stage_system_fire`, `fired.mails`) | wie oben | In-App + Mail | ja |

`transition_done` bleibt für Systemakteure stumm (M4 5.7); T09b braucht deshalb ein eigenes Kind. `params` tragen nur Anzeigewerte: `eventTitle`, `daysOpen`, `missing` (Teilmenge von `retrospective, outcome, howto, checklist`), bei `auto_archived` zusätzlich `howtoUnverified: bool`. `link` ist `/dossiers/<id>/nachbereitung`. Mailtexte unter `notifications/templates/de/<kind>.{subject,txt,html}.j2` (Sandbox, `StrictUndefined`, Betreff ohne CR/LF).

**Worker `worker/followup.py: send_followup_reminders`** (arq-Cron stündlich, Minute 20 UTC, `unique=True`, Timeout 300; Muster `send_due_reminders`): wählt `state = 'followup'` mit `entered_followup_at + 7 Tage <= now` (Eintritt = `max(at)` von `event_status_event` mit `to_state = 'followup'`, wie `worker/advance.py`), ruft `notify(..., dedupe_key = f"followup_reminder:{event_id}:{eintritt:%Y%m%d}")`. Genau eine Erinnerung je Eintritt; nach T10 beginnt ein neuer Eintritt und damit eine neue Erinnerung. Ohne Redis-Queue läuft der Job nicht (wie `send_due_reminders`, M4 Nachtrag). Die Erinnerung kommt **nach 7 Tagen** (PLAN 4.3), nicht erst vor T09b.

### 3.4 Eingabe der Nachbereitung: Endpunkte

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `PUT /api/events/{id}/outcome` | `event.edit` in der Organisation; Zustände `live` (nach `ends_at`) und `followup` | Body `OutcomeIn` (3.5), ersetzt `event.outcome` ganz; `If-Match` auf `event.rev` (428 ohne, 409 `conflict` mit `current`); schreibt eine Revision der Klasse `dossier`, erhöht `rev`, kein `public_seq`. In anderen Zuständen 409 `field_locked` |
| `POST /api/events/{id}/documents` (M4) | `event.edit` | der Rückblick braucht keine neue Route: `kind = retrospective` ist neu erlaubt (Titel Standard "Rückblick", `visibility = org`, `carryOver = false`; ein zweiter ergibt 409 `already_exists`); Änderungen über `PUT /documents/{id}` mit `If-Match`. Erlaubt in `live` (nach dem Ende) und `followup`; in `archived` gesperrt (M4 3.6) |
| `POST/DELETE /api/events/{id}/actions/verify-howto` | `event.submit` | wie 3.2 |

`EventOut` wächst um `outcome`, `howtoVerifiedAt`, `howtoVerifiedBy`, `formatId`, `format {slug, title}`, `derivedFromId`, `facts`, `locationPrecision`, `locationConfirmedAt`; `EventCard` um `formatSlug` und `howtoUnverified`; `dossier-counts` um `followupOpen` (Zahl der offenen Blocker von T09). `allowedActions` nennt `verify-howto`, `confirm-location`, `save-as-format`, `clone`.

### 3.5 `outcome` und Rückblick

`OutcomeIn` (Pydantic, camelCase, `extra=forbid`): `attendance: int >= 0 | null`, `costsCents: int >= 0 | null`, `revenueCents: int >= 0 | null`, `notes: str | null` (<= 2000, ohne Steuerzeichen außer Zeilenumbruch), `waived: bool = false`, `waivedReason: str | null` (<= 300). `waived = true` verlangt `waivedReason` mit mindestens 10 Zeichen (422 `waiver_reason_required`, Text "Verzicht braucht einen Grund.") und löscht die drei Zahlen. Beträge in Cent, Währung ist immer EUR (kein Währungsfeld; Vergleichsangebote bleiben davon getrennt). Der Auftrag nennt `costs_cents`; die Spalte hält `costsCents` (13.1.4). `outcome` steht nie in Feed, Karten oder Audit; in Revisionen steht es als Teil des Dossiers (nur Leser der Organisation sehen Revisionen, M3).

### 3.6 Platzhalter-Guards, die vor dem Pilot echt werden (M1 Abw. 4, M3 12.18)

- **`locationConfirmed` (`location_unconfirmed`, T04):** erfüllt, wenn `venue_id` gesetzt ist, oder `venue_text` leer ist, oder `location_confirmed_at IS NOT NULL AND location_precision <> 'hidden'`. Aktion `POST /api/events/{id}/actions/confirm-location` (Recht `event.approve`, wie `confirm-flyer`; Body `{precision: "exact"|"building"}`, nie `hidden`; Hinweistext im Dialog: "Der Ort ist öffentlich. Keine Privatadresse."): setzt Genauigkeit, Zeitstempel und Person, schreibt eine Revision der Klasse `critical` und erhöht in `live` `public_seq` (der Ort ändert sich öffentlich). Eine **Änderung von `venue_text`** setzt die Bestätigung zurück (`location_confirmed_at = NULL`, `location_precision = 'hidden'`), in `live` mit den Guards der kritischen Felder. Folge: ohne Bestätigung zeigt die View den freien Ortstext nicht (2.6), auch wenn jemand den Guard umgeht.
- **`factsValid` (`facts_invalid`, T02):** `event.facts` ist ein Pydantic-Union nach `category.required_profile` (PLAN 3.4, alle `extra=forbid`): `generic {capacity, budgetCents}`; `party {ageLimit ∈ 0|16|18, capacity, securityPlanDone, noisePermitRef, budgetCents}`; `meeting {agendaMd, quorumNeeded, protocolOwner}`; `trip {meetingPoint, priceText, minParticipants, maxParticipants, signupUrl, signupDeadline}`. Belegt ist nur "Party ohne `ageLimit`" (PLAN 4.4): das ist die einzige Pflicht; `trip` prüft `minParticipants <= maxParticipants`. Schreibweg `PUT /api/events/{id}/facts` (Recht `event.edit`, `If-Match`, Zustände wie die Textfelder (`_text_locked` in `pipeline/fieldclass.py`): offen in `idea`, `planning`, `live`, in `in_review` nur mit `event.approve`; Revision `dossier`); das Profil folgt der Hauptkategorie, ein Kategoriewechsel behält gleichnamige Felder und verwirft die übrigen mit Hinweis. Die Frontend-Stubs `facts.budgetCents` (M4 "Offen") werden verdrahtet.
- **Weiter Platzhalter** bleiben: `noOpenDuplicate` (M6), Wandzeit-Warnungen `time_ambiguous`/`time_gap` (M6, Zeitzonen-Matrix); M5 berührt sie nicht.

## 4. Klonen, Formate, "Letztes Mal"

### 4.1 Lesen archivierter Dossiers anderer Organisationen (löst M4 10.1.8)

`events/access.py: load_visible` bleibt unverändert (404 für fremde Organisationen). Neu `archive/access.py: load_archive_readable(session, principal, event_id) -> ArchiveRead`: liefert das Dossier mit der Beziehung `own` (es liegt im Lesebereich nach `readable_org_ids`) oder `foreign` (Zustand `archived`, Recht `library.read`); sonst 404. Für `foreign` gilt PLAN 5.4 Zeile "Dossier archived": **Kerndaten** (Titel, Kurztext, Beschreibung, Organisation, Kategorie, Format, Termin, Ortsname, Zustand, `outcome.attendance`) plus `shared`-Dokumente und -Anhänge; keine Kosten, keine Notizen, keine Checkliste (außer 4.2), keine Kommentare, keine Revisionen, kein `team`/`org`. `attachment_readable` bekommt den Zusatzast `foreign_archived`: `visibility = 'shared'` **und** `scan_status = 'clean'` **und** nicht ausgeblendet; die Wahrheitstabelle (M4 9.1) wächst um die Spalte "Beziehung zum Dossier". Lesepfade: `GET /api/archive/{id}` (`ArchiveEventOut`: Kerndaten, `documents[]` ohne Rumpf, `attachments[]`, `own: bool`), `GET /documents/{id}` und `GET /attachments/{id}/download|preview` akzeptieren zusätzlich den Archivpfad. Alles andere (PATCH, Transitionen, Kommentare, Checkliste, Angebote) bleibt 404 für `foreign`.

### 4.2 Klonen (E11, PLAN 7.4)

`POST /api/events/{id}/clone` (Recht `event.create` in der Zielorganisation; die Vorlage muss nach 4.1 lesbar und klonbar sein), Body `CloneIn` (`extra=forbid`): `startsAt` (Pflicht, tz-aware), `endsAt?` (Standard: `startsAt` + Dauer der Vorlage; ganztägige Vorlagen behalten ihre Tageszahl), `organizationId?`, `title?` (PLAN 7.4; Standard: Titel der Vorlage ohne Semester- und Jahresmarken, `strip_edition`). Die Zielorganisation ist `organizationId`, sonst die Organisation der Vorlage, falls die Person dort `event.create` hat, sonst ihre einzige solche Organisation, sonst 422 `organization_required`. Klonbar sind `archived` (alle Organisationen) sowie `live` und `followup` der eigenen; sonst 409 `not_a_template` (Text "Vorlage nicht mehr verfügbar."). Antwort 201 `CloneOut {event: EventOut, report: CarryOverLine[]}` mit `Location`. Das Ergebnis ist ein Dossier in `idea` mit `derived_from_id`, `origin_kind = internal`, `created_by` = Aufrufer:in, Revision 1 mit Notiz "Aus Vorlage …", Audit `EVENT_CLONE` (nur IDs). Kein `slug`, keine Mail, kein Übergang.

`GET /api/events/{id}/clone-preview?organizationId=` (Recht wie der Klon, ändert nichts) liefert dieselbe `report`-Liste plus `lastTime` (4.3); ein Test beweist, dass Vorschau und Klonbericht gleich sind. Die Tabelle steht **einmal** als Code (`archive/carry_over.py: CARRY_OVER`, reine Funktion `plan(source, relation, actor) -> list[CarryOverLine]`), die Vorschau, der Klon und die Oberfläche (I06) lesen sie.

| Teil | Eigene Organisation | Fremde Organisation (nur `archived`) | Mechanik und Grund (Textschlüssel `clone.reason.*`) |
|---|---|---|---|
| `title`, `summary`, `description_md`, `cost_text` | übernommen | übernommen | Titel ohne Semester/Jahr (`strip_edition`) |
| `primary_category_id`, `format_id`, `venue_id` | übernommen | übernommen | |
| `venue_text` | übernommen, `location_precision = hidden` | wie eigene | Ort muss neu bestätigt werden (3.6) |
| `organization_id` | Zielorganisation | Zielorganisation | |
| `facts` | übernommen, zurückgesetzt: `securityPlanDone = false`, `noisePermitRef`, `signupUrl`, `signupDeadline` leer | wie eigene, zusätzlich `budgetCents`, `priceText`, `meetingPoint`, `protocolOwner` leer | ablaufende Angaben; Kosten bleiben bei der Ursprungsorganisation (A13) |
| Dokumente mit `carry_over = true` (`howto`, `notes`, `mail_template`) | kopiert (Revision 1, Notiz "Aus Vorlage …", `verified_at/_by` leer, Sichtbarkeit bleibt) | nur `visibility = 'shared'`, Sichtbarkeit wird zum Standard der Art | **Anleitung:** hat das Format eine Master-Anleitung, wird das `howto` **nicht** kopiert; das Dossier zeigt einen Link auf `format.master_howto` (Auftrag), sonst Kopie. `retrospective` hat `carry_over = false` und wird nie kopiert |
| Checkliste | alle Punkte (auch eigene), `template_item_id` bleibt, `done_*`, `waived_reason`, `assignee_sub` zurückgesetzt; `due_offset_days` bleibt, fehlt er und war `due_at` von Hand gesetzt, wird er aus Vorlagen-Start und `due_at` (Ortsdaten) abgeleitet und auf -365..365 begrenzt; `due_at` neu aus `startsAt` (Regel M4 2.4), `due_manual = false` | nur Punkte mit `template_item_id` | freie Punkte fremder Organisationen können interne Namen tragen (13.2 D3) |
| Poster, `hero_attachment_id`, `flyer_checked_at`, Flyer-Bestätigungen | **nie** | **nie** | "Poster: Datum im Bild, bitte neu gestalten" (`clone.reason.poster`) |
| `image_exception` | **nie** | **nie** | gilt nur für die Event-ID (PLAN 4.3) |
| Vergleichsangebote, Businessplan, Verträge, jeder Anhang | **nie** | **nie** | Dateien werden nie kopiert; eigene Organisation sieht das Panel "Angebote der letzten Auflage" (4.3) |
| Social-Post-Texte | **nie** (13.1.9) | **nie** | M4 speichert sie nur an Bilddateien; ohne Datei gibt es keinen Entwurf |
| `ticket_url`, `website_url`, `publish_at`, `slug`, `public_seq`, `public_status`, `public_reason_*` | **nie** | **nie** | Link-Hosts sind kritisch (E07); `website_url` steht im PLAN nicht in der Übernahmeliste (13.1.10) |
| Kommentare, Revisionen, `outcome`, Rückblick, `howto_verified_*`, `submitted_by`, `approved_by` | **nie** | **nie** | gehören zur Ausgabe, nicht zur Vorlage |
| `shared`-Dokumente und -Anhänge der Vorlage | verlinkt | verlinkt | Panel "Aus der Vorlage" über `derived_from_id` (Archivpfad 4.1); keine Kopie von Dateien |

Der Klon ist **eine Transaktion** (Dossier, Revision, Dokumente mit Revision 1, Checklistenpunkte, `media_ref` der kopierten Dokumente). Dokumentbilder (`/api/media/images/<uuid>`) werden mit referenziert, nicht neu hochgeladen. Alle Fälligkeiten nutzen `checklist_due.recompute` (M4); die Antwort enthält `checklistRecomputed`.

### 4.3 "Letztes Mal" und Vorlagen-Suche

- `GET /api/events/{id}/last-time` (Recht: Lesen des Dossiers): Quelle ist `derived_from_id` (wenn nach 4.1 lesbar), sonst die jüngste lesbare `archived`-Ausgabe desselben Formats mit früherem Start. Antwort `{source {id, title, startsAt, state, organization {slug, short}, own}, attendance, costsCents, revenueCents, notes, retrospective {id, rev, bodyMd} | null, restricted: bool}`. **Eigene Organisation:** alles. **Fremde Organisation:** `attendance` und nur ein Rückblick mit `visibility = 'shared'`; `costsCents`, `revenueCents`, `notes` bleiben `null`, `restricted = true` (A13, E12, Auftrag). Leer: `null` mit 200 ("Noch keine Ausgabe").
- "Angebote der letzten Auflage": keine neue Route. Das Panel ruft `GET /events/{sourceId}/quotes` (M4 5.8) und zeigt die Antwort nur, wenn sie 200 ist (eigene Organisation mit Recht); sonst bleibt das Panel weg. Beträge stehen nirgends sonst.
- `GET /api/templates?q=&category=&organization=&format=&year=&limit=&offset=` (Recht `library.read`): klonbare Dossiers (4.2) mit Treffern aus derselben Abfrage wie die Suche (6.2, `scope=events`, aber nur klonbare Zustände). `TemplateCard`: `id, title, startsAt, allDay, state, organization {slug, name, short}, format {slug, title} | null, categories, attendance, howtoVerifiedAt, howtoUnverified, hasHowto, foreign, sharedDocuments, checklistItems`. Sortierung: Relevanz (nur mit `q`), `format.last_verified_at` absteigend (leer zuletzt), `starts_at` absteigend; die Gruppierung nach Format macht der Client (13.1.8).

### 4.4 Formate (I18)

| Methode, Pfad | Recht | Beschreibung |
|---|---|---|
| `GET /api/formats?q=&organization=&limit=&offset=` | `library.read` | `Page[FormatCard]`: `slug, title, organization, lastVerifiedAt, howtoStale, editions (Zahl lesbarer Ausgaben), lastEdition {id, title, startsAt}` |
| `GET /api/formats/{slug}` | `library.read` | `FormatOut`: Kopf, `defaults`, `descriptionMd`, `masterHowto {id, rev, title, verifiedAt, verifiedBy, bodyMd} | null`, `lastVerifiedAt`, `howtoStale`, `checklist {profile, template {slug, name}, items[]}` (die Vorlage des Profils, nur lesen), `mailTemplates[]` (die `mail_template`-Dokumente der jüngsten lesbaren archivierten Ausgabe, nur Verweise), `editions[]` (`id, title, startsAt, state, attendance, costsCents | null, howtoUnverified, foreign`; fremde Ausgaben nur `archived` und ohne Kosten) |
| `POST /api/formats` | `format.manage` oder `event.submit` in `organizationId` | `{slug, title, organizationId, defaults?, descriptionMd?}`; 409 `slug_taken` |
| `PATCH /api/formats/{slug}` | wie oben (für die Organisation des Formats) | `title?, defaults?, descriptionMd?, active?`; ohne ETag, letzter Schreiber gewinnt, Audit `FORMAT_UPDATE` (13.1.11) |
| `POST /api/formats/{slug}/howto` | wie oben | legt die Master-Anleitung an: Body `{fromEventId?}` kopiert das Howto-Dokument dieses lesbaren Dossiers (Revision 1), sonst Gerüsttext; 409 `already_exists` |
| `POST /api/formats/{slug}/verify` | wie oben | setzt `last_verified_at/_by` und die Prüfung der Master-Anleitung ohne T09 (Redaktionspflege) |
| `POST /api/formats/{slug}/new-edition` | `event.create` in der Zielorganisation | `{startsAt, endsAt?, organizationId?}`: gibt es eine klonbare, lesbare archivierte Ausgabe, wird die jüngste geklont (4.2); sonst ein neues Dossier in `idea` aus `defaults` (Titel = Formattitel, Kategorie, Ort, Dauer, danach `apply-template` mit `checklistProfile`). Antwort wie `CloneOut` (`report` leer bei Neuanlage) |
| `PUT /api/events/{id}/format` | `event.edit` | `{formatId: uuid | null}` (Zustände `idea` bis `followup`); das Format muss zur Organisation des Dossiers gehören oder der Aufrufer ist `editor` (sonst 422 `format_foreign`) |
| `POST /api/events/{id}/save-as-format` | `event.submit` in der Organisation (Or, Ap, Ed; Voreinstellung D9) | "Als Format speichern" (4.5) |

Die Master-Anleitung ist ein Dokument mit `format_id`; lesen und schreiben läuft über die Dokument-Routen von M4, deren Berechtigung eine Fassung für Format-Dokumente bekommt (`dossier/documents.access`): Lesen `library.read` (Sichtbarkeit `shared`), Schreiben `format.manage` oder `event.submit` in `format.organization_id`. Format-Dokumente hängen an keinem Dossier-Zustand; die Sperre für `archived` und `withdrawn` (M4 3.6) gilt nur für Dossier-Dokumente. `PUT /documents/{id}` mit `If-Match` wie M4; Autosave-Entwurf wie M4. Die Warnung "Anleitung seit über 12 Monaten ungeprüft" ist `howtoStale`.

### 4.5 "Als Format speichern"

`POST /api/events/{id}/save-as-format {slug, title, defaults?}`: das Dossier muss lesbar sein und noch kein `format_id` haben (409 `already_in_format`). In einer Transaktion: Format anlegen (`organization_id` = Organisation des Dossiers; `defaults` aus dem Dossier: `categoryId = primary_category_id`, `venueId = venue_id`, `durationMinutes` = Dauer auf 15 Minuten gerundet, `checklistProfile` = `required_profile` der Hauptkategorie), hat das Dossier ein `howto`-Dokument, wird es als Master-Anleitung kopiert (Revision 1, Notiz "Aus Dossier …", `visibility = shared`, **nicht** geprüft), `event.format_id` setzen, Revision der Klasse `dossier`, Audit `FORMAT_CREATE`. Antwort 201 `FormatOut`. Das Frontend zeigt die bisher ausgeblendete Aktion "Als Vorlage für das Format speichern" (M4 "Offen") im Dossierkopf.

## 5. Bibliothek (I19)

Die Bibliothek ist eine **Sicht**, keine eigene Ablage (Abweichung 13.1.3): sie listet, was fremde Organisationen und Formate bewusst geteilt haben. Recht: `library.read` (jede Rolle, `member` eingeschlossen). Eine eigene Verwaltung mit `library.manage` (PLAN 7.3 Ebene 3, `owner_kind = library`) bauen wir in M5 nicht (13.2 D14).

`GET /api/library?q=&kind=&category=&organization=&year=&format=&limit=&offset=` → `Page[LibraryItem]` mit `facets`:

| Quelle | Aufnahme in die Liste |
|---|---|
| Dokumente | `visibility = 'shared'`, `kind IN (howto, notes, mail_template)`, Dossier in `archived`; dazu die Master-Anleitungen aller Formate (`format_id`, immer `shared`) |
| Anhänge | `visibility = 'shared'`, `scan_status = 'clean'`, `retired_at IS NULL`, Dossier in `archived`; eingeschränkte Arten können wegen des CHECK nie `shared` sein, Poster und Social-Bilder sind nicht ausgeschlossen (das Poster bleibt `org`, solange niemand es teilt) |
| nicht | Rückblicke (`retrospective`), `team`/`org`-Zeilen, Zeilen nicht archivierter Dossiers, `infected`/`pending`/`error`, ausgeblendete Fassungen |

`LibraryItem`: `kind: document|attachment`, `id`, `title` (Dokumenttitel oder `displayName`), `subKind` (Dokumentart oder Anhangsart), `source {type: event|format, id, title, startsAt, organization {slug, short}, own}`, `categories`, `year` (Jahr des Starts, Ortszeit), `verifiedAt`, `updatedAt`, bei Anhängen `mime`, `sizeBytes`. Facetten: `category`, `organization`, `year`, `kind` mit Zählern über die gefilterte Treffermenge (die obersten 20 Werte je Facette). `q` sucht bei Dokumenten über `document.search_tsv` plus Trigramm auf dem Titel (6.2), bei Anhängen mit `ILIKE` auf `display_name` (`escape_like`). Der Rechtefilter steht **im SQL**, nie als Nachfilter im Client oder in Python.

- Lesen eines Eintrags: `GET /documents/{id}`, `GET /attachments/{id}/download|preview` über den Archivpfad (4.1); die Liste enthält nie einen Text, nur Titel und Quelle.
- `POST /api/library/documents/{id}/adopt {eventId}` ("In Dossier übernehmen", Recht `event.edit` im Ziel-Dossier, Zustand nicht `archived`/`withdrawn`): kopiert das Dokument in das Ziel-Dossier (Revision 1, Notiz "Aus Bibliothek übernommen: <Titel>", `verified_*` leer, `carry_over = true`); `howto` wird zu `notes`, wenn das Ziel schon eine Anleitung hat (409 sonst nicht nötig). Anhänge werden nicht kopiert, nur verlinkt (Datei-Duplikate und Scan wären ein zweiter Upload-Pfad).
- Leer: "Die Bibliothek ist leer. Gute Anleitungen aus Dossiers lassen sich hierher übernehmen." (PLAN I19). "Hierher übernehmen" heißt: Sichtbarkeit `shared` setzen, sobald das Dossier archiviert ist (M4 `PATCH /documents` bzw. `PATCH /attachments`).

## 6. Interne Suche (I20)

### 6.1 Schnittstelle

`GET /api/search?q=&scope=events|documents|formats&state=&org=&year=&category=&format=&limit=&offset=` (Recht `library.read`; Pfad `/api/search`, Router in `app/modules/search/`). `scope` Standard `events`. `q`: 2 bis 100 Zeichen; kürzer als 2 ergibt eine leere Trefferliste (Muster `U modules/search/service.py`, die Palette fragt bei jedem Tastendruck), länger als 100 ergibt 422 `query_too_long` (Text "Suchbegriff zu lang (höchstens 100 Zeichen)."). `state` ist wiederholbar, `org` ist der Slug, `year` das Jahr des Starts in Ortszeit, `limit` 1..50 (Standard 20). `SET LOCAL statement_timeout = '2s'` in der Transaktion der Suche (PLAN 7.7); ein Abbruch ergibt 503 `search_timeout`. Schreibzugriffe gibt es nicht; Ratenbegrenzung über `shared/ratelimit.py` je Person.

Antwort `SearchOut`: `q`, `scope`, `total`, `hits[]`, `facets {state[], organization[], year[], category[], format[]}` (je `{value, label, count}`), `suggestion: string | null`. `SearchHit`: `kind: event|document|format`, `id`, `title`, `subtitle` (Organisation und Datum, bei Dokumenten das Dossier), `state?`, `startsAt?`, `organization {slug, short}`, `format {slug, title} | null`, `howtoVerifiedAt?`, `howtoUnverified?`, `foreign: bool`, `link` (interner Pfad), `rank`, `highlights: [{field, segments: [{text, hit}]}]`. **Hervorhebung ohne HTML:** `ts_headline('de_unaccent', text, tsquery, 'StartSel=' || chr(1) || ',StopSel=' || chr(2) || ',MaxFragments=1,MaxWords=18,MinWords=6')` liefert Steuerzeichen als Markierung (gemessen: sie bleiben im Ergebnis erhalten, eigene HTML-Tags im Text gehen verloren), der Server schneidet an `chr(1)`/`chr(2)` in Segmente; das Frontend rendert Segmente mit `<mark>` aus Text, nie per `innerHTML`. Treffer ohne FTS-Anteil (nur Trigramm) tragen keine Hervorhebung; der Client markiert dann das Suchwort im Titel (Hilfe wie `U features/search/highlight.ts`).

`suggestion`: bei null Treffern das Titelwort (>= 5 Zeichen) lesbarer Dossiers und Formate mit der höchsten `word_similarity(q, wort)` im Fenster 0,3 bis 0,5 (Beispiel gemessen: "Kinabnd" zu "Kinoabend", 0,38); der Client fragt "Meintest du „Kinoabend“?" (I20).

### 6.2 Abfrage (Rechtefilter in SQL, FTS plus Trigramm)

1. **Sichtbarkeit zuerst, vor der Suche (PLAN 7.7):** Dossiers: `organization_id IN readable_org_ids` oder eigener Vorschlag (`events/access.visible_events_query`), **oder** `state = 'archived'` (Beziehung `foreign`, 4.1). Dokumente: Dossier sichtbar **und** (Beziehung `own` mit `visibility`-Regel von M4 3.7: `team` nur in Organisationen mit `event.submit` oder `dossier.read_restricted`, die Menge kommt aus `org_ids_for`, `None` heißt überall) **oder** `foreign` mit `visibility = 'shared'`; Format-Dokumente nur `shared`. Formate sind für alle mit `library.read` sichtbar. Gesperrte Zeilen kommen weder in Treffer noch in Facetten noch in `total` (ein Test vergleicht `total` mit der Länge der vollständig durchgeblätterten Treffer).
2. **FTS:** `tsquery = websearch_to_tsquery('de_unaccent', q) || websearch_to_tsquery('de_unaccent', translit(q))` mit `translit`: `ae→a, oe→o, ue→u` (ß und Umlaute löst `unaccent` selbst auf). Grund (gemessen): "Huettencafe" trifft "Hüttencafé" im FTS nicht (`'huettencaf'` gegen `'huttencaf'`), "Huttencafe" trifft; ebenso "Praesidium"/"Präsidium", "Loeten"/"Löten". Rang `ts_rank`, `setweight`-Gewichte aus 2.4.
3. **Trigramm-Zusatz** (Tippfehler und Komposita) **je Suchwort**, nicht für die ganze Eingabe, auf `immutable_unaccent(titel)`: für jedes Wort `w` der Eingabe (>= 3 Zeichen) gilt `FTS(w) OR vorwärts word_similarity(w, titel) >= 0.5 OR rückwärts` (je Titelwort ab 5 Zeichen aus `regexp_split_to_table(titel, '[^[:alnum:]äöüßÄÖÜ]+')`: `word_similarity(titelwort, w) > 0.6`); alle Wörter müssen zutreffen (UND, wie `websearch_to_tsquery`). Kürzere Wörter und Eingaben mit Anführungszeichen, `-` oder `or` (websearch-Syntax) laufen nur über FTS. Grund für "je Wort": gemessen trifft die ganze Eingabe "Movienight Halloween" den Titel "Movienight: Whiplash" mit 0,52 (Rauschen), das Einzelwort "Halloween" trifft ihn nicht. Gemessen auf dem Dev-Stack (Temp-Tabelle, zurückgerollt): "Kinoabnd" → "Kinoabend" 0,67; "Parti" → "Party" 0,67; "LAN Partie" → "LAN Party" 0,73; "Skiausfart" → "Skiausfahrt Davos" 0,73; "game togther" → "Game Together" 0,69; "Camposfest" → "Campusfest" 0,57; "Kino" → "Kinoabend" 0,80; "Fachschaftssitzung" → Titelwort "Sitzung" rückwärts 0,75 und Titelwort "Fachschaft" 0,91 (vorwärts nur 0,32, über den ganzen Titel "STUPA-Sitzung" rückwärts nur 0,46, deshalb **je Titelwort**); "Loeten" bleibt im Trigramm unter 0,4 und braucht `translit`; Rauschen: "Cafe" → "Campusfest" 0,40 bleibt unter der Schwelle.
4. **Gesamtrang** = Summe über die Wörter von (FTS-Rang oder Trigramm-Rang × 0,5) + 1,0 bei FTS-Treffer im Titel; Gleichstand nach `starts_at` absteigend, dann `id`. Zusätzlich zählen lesbare Dokumente des Dossiers als Gewicht D: ein Dossier erscheint auch, wenn nur seine Anleitung den Begriff enthält ("Popcornmaschine"), mit Rang × 0,1. Organisations- und Ortsnamen im Trigramm-Zusatz mit Faktor 0,5 (PLAN 7.7).
5. **Eingabe:** `q` ist immer ein gebundener Parameter; `%` und `_` in `q` wirken nie als Platzhalter (`escape_like` nur dort, wo `ILIKE` benutzt wird); `\0` in `q` ergibt 422. Facetten laufen über dieselbe CTE `hits` (keine zweite Rechtefilter-Fassung).
6. **Vorlagen-Suche** (4.3) und **Bibliothek** (5) rufen dieselbe Abfragefunktion `search/query.py: build(scope, principal, filters)` auf, damit es genau eine Stelle für den Rechtefilter gibt.

### 6.3 Palette (Strg/Cmd+K)

Eine globale Palette im Rahmen `rail` (Dialog `app-dialog`, Handy Bottom-Sheet; Fokusfalle, Esc schließt, `role=combobox` mit Listbox, Treffer als Liste mit `aria-activedescendant`, Ergebniszahl in einer `aria-live`-Region). Gruppen laut Auftrag: **Dossiers** (`GET /api/search?scope=events&limit=5`), **Formate** (`scope=formats&limit=3`), **Aktionen** (clientseitig: "Neues Event", "Neu aus Vorlage", "Als Format speichern" nur im Dossierkontext) und **Navigation** (Seitenliste aus der Routentabelle, gefiltert nach Rechten, Muster `U features/search/page-index.service.ts`). Zwei Anfragen laufen parallel (je eigene Sitzung), 200 ms Verzögerung, ältere Antworten werden verworfen. PLAN 15.1 I20 nennt zusätzlich Dokumente, Orte und Organisationen als Gruppen; der Auftrag beschränkt die Palette auf die vier Gruppen oben (13.1.7). Die Seite `/archiv` (11.4) bedient Dokumente und alle Facetten.

### 6.4 Die 20 Mustersuchen (`tests/fixtures/search/queries.yaml`)

Korpus `tests/fixtures/search/corpus.yaml` (Dossiers, Dokumente, Formate; **Filmtitel und Daten sind synthetisch**, nur Muster und Zahlen stammen aus KARTE 2.7 und dem Auftrag, 13.2 D15). Jede Suche nennt Eingabe, Hauptperson (Konto aus dem Dev-Seed), `scope`, Filter und die **genau erwartete Menge** an Titeln (Reihenfolge nur dort, wo `first:` steht). Die Fälle 1 und 4 bis 12 stützen sich auf die Messungen in 6.2; die Fälle 2, 3 und 13 bis 20 sind Regeln, deren Beleg erst der Test ist.

| # | Eingabe (`scope`, Filter) | Erwartung | Prüft |
|---|---|---|---|
| 1 | `Fachschaftssitzung` | "Sitzung FSI", "STUPA-Sitzung" und, weil das Wort "Fachschaft" im Eingabewort steckt, "Sommerfest der Fachschaft" | Komposita, Trigramm rückwärts je Titelwort (Auftrag) |
| 2 | `movienight` | "Movienight: Whiplash" (`first:`) und die übrigen Movienights | FTS, Groß/Klein |
| 3 | `Movienight Halloween` | nur "Movienight: Halloween-Special" | UND-Semantik von `websearch_to_tsquery` |
| 4 | `Hüttencafe` | "Hüttencafé" | `unaccent` |
| 5 | `Huettencafe` | "Hüttencafé" | `translit` |
| 6 | `Praesidium` | "Offenes Präsidium" | `translit`, ae |
| 7 | `Weissbier` | "Weißbier-Abend" | ß |
| 8 | `Kinoabnd` | "Kinoabend" | Tippfehler ein Buchstabe |
| 9 | `Parti` | "Party", "LAN Party" | Wortanfang |
| 10 | `LAN Partie` | "LAN Party", "FSI LAN-Party 2026" | Tippfehler, Mehrwort |
| 11 | `Skiausfart` | "Skiausfahrt Davos" | Tippfehler |
| 12 | `game togther` | "Game Together" | Tippfehler, klein |
| 13 | `Popcornmaschine` | das Dossier, dessen **Anleitung** das Wort enthält | Gewicht D (Dokument) |
| 14 | `Technikverleih` (`scope=documents`) | die Mailvorlage "Anfrage Technikverleih" | Dokumente |
| 15 | `Sitzung`, `org=fsi` | nur FSI-Sitzungen | Organisationsfilter |
| 16 | `Movienight`, `year=2025` | nur Ausgaben mit Start 2025 (Ortszeit; eine Ausgabe am 01.01. 00:30 Berlin zählt nach Berlin, nicht UTC) | Jahresfilter, Zeitzone |
| 17 | `Movienight`, `state=archived`, als `organizer-makers` | nur archivierte Ausgaben; keine `live`/`followup` der FSI | fremde Organisation: nur `archived` (4.1) |
| 18 | `100%` | keine Treffer, kein Fehler, kein Platzhalter-Effekt | Eingabe |
| 19 | `Kontext-Notiz` (Wort nur in einem `team`-Dokument der FSI), als `organizer-makers` und als `member` | keine Treffer; als `organizer-fsi` ein Treffer | Dokumentsichtbarkeit |
| 20 | `x`, und ein Wort mit 101 Zeichen | leere Liste bzw. 422 `query_too_long` | Längen |

Dazu `test_search_total_equals_walked_hits`, `test_search_never_returns_restricted_rows` (Kanarienvogel, 10.4) und der Fall "keine Treffer mit Vorschlag" (`Kinabnd` → `suggestion = "Kinoabend"`).

## 7. Interner Kalender

`GET /api/events?view=calendar&from=&to=` (gleicher Pfad und gleiche Filter wie M3: `state`, `organization`, `category`, `mine`, `q`; Recht `library.read`; die Antwortunion `Page[EventCard] | BoardOut` wächst um `CalendarOut`). `from` und `to` sind **Pflicht** und Ortsdaten (`YYYY-MM-DD`, einschließlich); der Zeitraum darf höchstens 100 Tage umfassen (sonst 422 `range_too_large`; ein Monatsraster mit Randtagen sind höchstens 42). Ausgewählt wird nach Überschneidung (`ends_at >= von-Mitternacht AND starts_at < bis-Folgetag-Mitternacht`, Ortszeit) im Lesebereich des Aufrufers (`visible_events_query`), `withdrawn` nur mit `state=withdrawn`; höchstens 500 Einträge (`truncated: true` darüber). Antwort `{from, to, entries[], truncated}` mit `entries[] = {id, title, startsAt, endsAt, allDay, startsOn, endsOn, state, publicStatus, organization {slug, short, colorToken}, category {slug, colorToken} | null, venueName | null, howtoUnverified}` (Token-Namen, nie Hex). Serien erscheinen als Einzeltermine; Serienbalken, Ausnahmen und Plan kommen mit M7.

`app-calendar-grid` (`shared/ui/calendar-grid`, Muster `U features/meetings/meetings-calendar`): Eingaben `entries`, `mode: month|week`, `anchor` (Datum), Ausgaben `entryOpen`, `rangeChange`. Monat: Montag bis Sonntag, 6 Zeilen, `role=grid` mit Pfeiltasten, Tab springt aus dem Raster, "+n" bei mehr als drei Einträgen je Tag (öffnet ein `app-side-sheet` mit der Tagesliste), mehrtägige Einträge auf jedem Tag, den sie berühren, ganztägige zuerst. Woche: sieben Spalten mit Tagesliste, keine Stundenachse. **Handy (unter 768 px): Agenda-Liste** je Tag statt Raster (Upstream hat dort keinen Kalender, die Liste ist die erste Wahl). "Heute" über eine Token-Uhr (`OVERVIEW_NOW`-Muster), Datumsformat über `formatEventTime(iso, tz)` in `Europe/Berlin` (nie UTC-Hilfen, `lesen/wf-frontend.md` Nr. 15). Farbe je Organisation über `colorToken`, der Zustand steht als Text (`app-status-text`) bei allem außer `live`/`approved`, Farbe allein trägt nie. Route `/kalender` (Rahmenflag `wide`), Umschalter Liste | Kalender in I04 verlinkt dorthin und übernimmt die Filter als Query. Der Navigationseintrag `calendar` steht in der Rail und der Bottom-Bar.

## 8. ICS: `GET /ics/all.ics` und `GET /ics/k/<category-slug>.ics`

Öffentlich, nur lesend, über die Rolle `events_public` und die View aus 2.6 (E14); der Router liegt in `publicapi/ics_router.py` und wird in `create_app` **ohne** `/api`-Präfix eingebunden (`app.include_router(ics_router)`). Es gibt keine Session, kein Cookie (`Set-Cookie` nie, Test wie `test_public_no_set_cookie`), kein CORS, keine Abfrageparameter (sie werden ignoriert). Profil-Token (`/ics/p/<token>.ics`) gehören zu Stufe B und werden nicht gebaut.

### 8.1 Inhalt und Fenster

- `/ics/all.ics`: alle Zeilen der View im Fenster; `/ics/k/<slug>.ics`: Zeilen, deren Hauptkategorie `slug` ist **oder** deren Elternkategorie `slug` ist (Fachschaft 138 mit 173/174/175). Unbekannter oder formal ungültiger Slug (`^[a-z0-9][a-z0-9-]{0,59}$`): 404 Problem+JSON. Eine Kategorie mit `active = false` liefert weiter einen Kalender (Abos dürfen nicht brechen).
- **Nur `live` plus `public_status`:** die View enthält `live`, `followup`, `archived`; ICS nimmt dieselben Zeilen, weil ein vergangener Termin im Fenster ein gültiger Kalendereintrag bleibt. `cancelled` bleibt als `STATUS:CANCELLED` im Kalender (nichts wird gelöscht). Entwürfe, nicht freigegebene und `withdrawn` sind nie darin (View).
- **Fenster:** `ends_at >= now - 3 Monate` und `starts_at <= now + 12 Monate` (PLAN 8.3); sortiert nach `starts_at`, `id`. `now` kommt aus der Uhr des Aufrufers (Snapshot-Zeit beim Bau, im Test fest).

### 8.2 Kopf, Zeitzone, Ereignis

Zeilenende überall `CRLF`, Zeichensatz UTF-8, feste Eigenschaftsreihenfolge (deterministisch, Golden-Tests):

```
BEGIN:VCALENDAR / VERSION:2.0 / PRODID:-//STUPA Events//Kalender//DE / CALSCALE:GREGORIAN / METHOD:PUBLISH
X-WR-CALNAME:STUPA Events  (Kategorie: "STUPA Events: <Name>") / X-WR-TIMEZONE:Europe/Berlin
REFRESH-INTERVAL;VALUE=DURATION:PT1H / X-PUBLISHED-TTL:PT1H
BEGIN:VTIMEZONE (Europe/Berlin, 8.3) … END:VTIMEZONE
BEGIN:VEVENT
UID, DTSTAMP, LAST-MODIFIED, SEQUENCE, SUMMARY, DTSTART, DTEND, STATUS, DESCRIPTION, LOCATION, CATEGORIES, URL
END:VEVENT … END:VCALENDAR
```

| Eigenschaft | Regel |
|---|---|
| `UID` | `<event.id>@events.reutlingen.university`, nie neu vergeben (`settings.ics_uid_domain`, Standard genau dieser Wert; eine Änderung würde jede Abo-Kopie verdoppeln und steht deshalb im Test `test_ics_uid_domain_is_pinned`) |
| `DTSTAMP`, `LAST-MODIFIED` | `updated_at` der View in UTC mit `Z` (deterministisch, nicht die Bauzeit) |
| `SEQUENCE` | `public_seq` |
| `SUMMARY` | Titel, escaped (8.4) |
| `DTSTART`, `DTEND` | zeitlich: `DTSTART;TZID=Europe/Berlin:20261031T200000`; über Mitternacht und mehrtägig wie gespeichert (kein Zerlegen). **Ausnahme:** liegt der Instant in der wiederholten Stunde der Umstellung (beide Durchläufe, z. B. 25.10.2026 02:30 CEST = 00:30Z und 02:30 CET = 01:30Z), gibt der Schreiber `DTSTART:20261025T003000Z` bzw. `DTSTART:20261025T013000Z` aus, weil eine Ortszeit mit TZID dort mehrdeutig wäre (Entscheidung D8; im Integrationslauf auf den ersten Durchlauf erweitert, 13.1.18). Ganztägig: `DTSTART;VALUE=DATE:20261031` und `DTEND;VALUE=DATE:<ends_on + 1 Tag>` (exklusiv, `DTEND` immer vorhanden). Lücke (02:30 am 28.03.) kann als Instant nicht entstehen |
| `STATUS` | `scheduled` → `CONFIRMED`; `cancelled` → `CANCELLED`; `postponed` → `TENTATIVE` (Voreinstellung D7) |
| Verschoben | `postpone` mit neuem Termin ändert `starts_at/ends_at` und erhöht `public_seq` (M3 `actions_service.postpone`); der Kalender zeigt neue `DTSTART` und höhere `SEQUENCE`, `UID` bleibt. Ohne neues Datum bleibt der alte Termin mit `STATUS:TENTATIVE` |
| `DESCRIPTION` | `summary` (falls vorhanden); bei `cancelled`/`postponed` zuerst eine Zeile "Abgesagt: " bzw. "Verschoben: " plus `public_reason_text` (öffentlicher Text, <= 140 Zeichen, nur von Prüfenden gesetzt, A05); nie `description_md`, nie interne Gründe |
| `LOCATION` | `venue_name`; bei `venue_address`/`venue_city` zusätzlich `", Adresse, Stadt"`; private Orte "Treffpunkt auf Anfrage"; kein `GEO` (Stufe C) |
| `CATEGORIES` | Namen der Haupt- und Elternkategorie (escaped, durch Komma getrennt) |
| `URL` | `<public_base_url>/e/<slug>` |
| nie | `ORGANIZER` (keine Adressen), `ATTENDEE`, `VALARM`, `GEO`, `ATTACH`, Beschreibung des Dossiers, jede `X-`-Eigenschaft außer `X-WR-*` und `X-PUBLISHED-TTL` |

### 8.3 VTIMEZONE

Der Schreiber fügt **immer** einen `VTIMEZONE`-Block `Europe/Berlin` ein, sobald ein Ereignis `TZID` nutzt (gegen PLAN 8.3 "kein VTIMEZONE", Auftrag gewinnt, 13.1.2). Inhalt als Konstante (Regeln der EU seit 1996):

```
BEGIN:VTIMEZONE / TZID:Europe/Berlin / X-LIC-LOCATION:Europe/Berlin
BEGIN:DAYLIGHT / TZOFFSETFROM:+0100 / TZOFFSETTO:+0200 / TZNAME:CEST / DTSTART:19700329T020000 / RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU / END:DAYLIGHT
BEGIN:STANDARD / TZOFFSETFROM:+0200 / TZOFFSETTO:+0100 / TZNAME:CET / DTSTART:19701025T030000 / RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU / END:STANDARD
END:VTIMEZONE
```

Test `test_vtimezone_matches_zoneinfo`: für jede Ortszeit stündlich von 2025 bis 2030 stimmt der aus den beiden RRULEs berechnete Offset mit `zoneinfo.ZoneInfo("Europe/Berlin")` überein (der 25.10.2026 ist der letzte Sonntag im Oktober, der 28.03.2027 der im März).

### 8.4 Schreiber (`publicapi/ics/`)

Eigener Schreiber ohne neue Laufzeit-Abhängigkeit (`writer.py`, `fold.py`, `escape.py`, `timezone.py`); `icalendar` kommt nur als Entwicklungs-Abhängigkeit zum Gegenlesen in Tests (Upstream nutzt es lazy und schreibt UTC, `U calendar/ics.py`; hier sind feste Byte-Folgen und `TZID` gefordert). **Escaping** nach RFC 5545 §3.3.11: `\`→`\\`, `;`→`\;`, `,`→`\,`, Zeilenumbruch→`\n`; alle Zeichen aus `CONTROL_CHARS` (inkl. CR, LF, NEL, U+2028/2029) werden vor dem Escapen durch ein Leerzeichen ersetzt (bei `DESCRIPTION` Zeilenumbrüche vorher zu `\n`). **Faltung** bei 75 **Oktetten** je physischer Zeile (ohne `CRLF`), Fortsetzungszeilen beginnen mit genau einem Leerzeichen, das mitzählt; nie in der Mitte eines UTF-8-Zeichens (ZWJ-Emoji werden an Zeichengrenzen geteilt, was RFC-konform ist). **CR/LF-Sperre:** Titel, Ortstexte und Taxonomienamen können dank 2.5 kein CR/LF tragen; der Schreiber glaubt das nicht, sondern bereinigt trotzdem (Property-Test `test_ics_text_never_injects`, hypothesis: für jede Zeichenkette entsteht genau ein `VEVENT` mit den erwarteten Eigenschaften, gelesen mit `icalendar`).

### 8.5 Auslieferung

Antwort 200 `Content-Type: text/calendar; charset=utf-8`, `Cache-Control: public, max-age=3600`, `ETag` (Hash der Bytes), 304 bei `If-None-Match`, `Content-Disposition: inline; filename="stupa-events.ics"` (ASCII), `X-Robots-Tag: noindex`, kein `Set-Cookie`. Die Bytes kommen aus dem Worker-Snapshot (9.5), nur bei Fehlen aus der View. **Access-Log ohne Query:** `deploy/web/nginx.conf` setzt in `location /ics/` `access_log … ev_noquery;`, die App loggt den Pfad ohne Query (Token gibt es hier keine, die Regel gilt trotzdem einheitlich, A08). Middleware: `app/middleware.py` und `app/shared/errors.py` führen das öffentliche Präfix als Liste (`/api/public/`, `/ics/`), damit `/ics/*` weder das CSRF-Cookie bekommt noch ohne `X-Robots-Tag` ausgeliefert wird; `tests/unit/test_route_authz_inventory.py` kennt `/ics/` als öffentliches Präfix und erzwingt, dass dort keine Abhängigkeit `get_session`/`get_current_principal` hängt.

### 8.6 Golden-Tests (`backend/tests/golden/ics/*.ics`)

Die Eingabe steht als Sicht-Zeilen in `tests/unit/publicapi/golden_cases.py`, die Golden-Datei wird byte-genau verglichen (`UPDATE_GOLDEN=1` schreibt sie neu, nur von Hand und mit Diff-Review). `DTSTAMP` kommt aus der festen `updated_at` der Eingabe.

| Datei | Fall |
|---|---|
| `movienight-ws26.ics` | die sieben Termine WS26/27 (Di 7, Do 5, Fr 5, Mo 4, Mi 2 ergeben die 23 Kopien des Bestands, hier die 7 des laufenden Semesters) inklusive Halloween-Doppel Sa 31.10.2026 20:00 bis 23:30 und 23:45 bis 01:30 (PLAN 3.6): zwei VEVENTs, Ende über Mitternacht |
| `cancelled.ics` | abgesagt: `STATUS:CANCELLED`, `SEQUENCE` +1, Grund-Zeile in `DESCRIPTION` |
| `postponed.ics` | verschoben mit neuem Datum: neue `DTSTART`, `SEQUENCE` 2, gleiche `UID`; und ohne Datum: `TENTATIVE` |
| `all-day.ics` | ganztägig, ein Tag (`VALUE=DATE`, `DTEND` = Folgetag) |
| `multi-day.ics` | mehrtägig, zeitlich: FSI-LAN-Party 25.09.2026 17:00 bis 27.09.2026 01:00 (Z02 der Zeitzonen-Matrix); und ganztägig über drei Tage |
| `dst-2026-10-25.ics` | Termin 24.10. 22:00 bis 25.10. 04:00 über die Umstellung; Termin 25.10. 02:30 CEST (`TZID`) und derselbe Instant in der zweiten Stunde (`Z`-Form, 8.2) |
| `umlauts-fold.ics` | `Hüttencafé`, `ß`, Emoji, ZWJ-Folge, Titel über 75 Oktette (Faltung), Komma und Semikolon im Ortsnamen |
| `crlf-attempt.ics` | Sicht-Zeile mit CR/LF, `BEGIN:VALARM` und `URL:` im Titel (so nicht aus der Datenbank erreichbar, 2.5): erwartet genau ein VEVENT, kein VALARM, Text bereinigt |

Zusätzlich `test_ics_unfold_roundtrip` (entfalten ergibt den Ausgangstext, jede physische Zeile <= 75 Oktette), `test_ics_parses_with_icalendar` (jede Golden-Datei lesbar, `UID`s eindeutig, `DTEND >= DTSTART`), `test_ics_order_is_deterministic`.

## 9. Feed Schema 2, vollständig

`GET /api/public/feed/events` bleibt unter `/api/public/` (Rolle `events_public`, View aus 2.6). Das JSON-Schema `backend/tests/schema/feed-v2.json` ist der Vertrag (Schemathesis und Snapshot); es wird in M5 zur Quelle der Wahrheit für Felder und Muster und wächst additiv gegen den M1-Stand. Der Name bleibt Schema 2 (E15), weil kein Verbraucher live ist; alle Änderungen gegenüber M1 sind additiv.

### 9.1 Hülle und Felder

Hülle `{schema: 2, generatedAt, nextCursor, items[]}` (`nextCursor`: `string | null`, neu). Ein Item (camelCase, `additionalProperties: false`):

| Feld | Typ und Regel |
|---|---|
| M1-Felder | `id, slug, title, summary, startsAt, endsAt, allDay, tzid, status, organization {id, slug, name, short}, venueText, statusReason, categories[], image {url, width, height, alt, credit} | null, url` bleiben (`startsAt`/`endsAt` in UTC mit `Z`, `tzid = Europe/Berlin`) |
| `startsOn`, `endsOn` | `date | null`, nur bei `allDay` (neu, 2.2); `endsOn` ist der letzte Tag, einschließlich |
| `categories[]` | `[{slug, name, kind}]`, Hauptkategorie zuerst, dann die Elternkategorie (`fachschaft`); `kind ∈ format|fachschaft|partner`. Der Auftrag schreibt `type`, M1 und die Kategorie-API nutzen `kind` (13.1.1) |
| `format` | `{slug, title} | null` (neu) |
| `statusReason` | `null` bei `scheduled`, sonst `{code ∈ none|room|speaker|illness|registration|weather|other, text | null}`; der Freitext (<= 140) ist öffentlich und nur von Prüfenden gesetzt (A05); der interne Grund (`event_status_event.note`) steht **nie** hier |
| `venue` | `{name, address | null, city | null} | null` (neu): `name` = `venue_name`, `address` nur bei `public_precision = exact`, `city` bei `exact`/`building`; privater Ort: nur `name = "Treffpunkt auf Anfrage"`; ohne öffentlichen Ort `null`. `venueText` bleibt als Alias von `venue.name` bei nicht privatem Ort bestehen (M1-Vertrag; private Orte liefern dort weiter `null`) |
| `ticketUrl`, `websiteUrl`, `costText` | `string | null` (neu, PLAN 8.2; Text-Klasse, E07; Voreinstellung D2) |
| `textHtml` | `string | null` (neu, PLAN 8.2): `description_md` serverseitig zu HTML (9.4) |
| `sequence` | `public_seq` (neu) |
| `updatedAt` | `updated_at` der View, UTC `Z` (neu) |

Nicht im Feed, nie: Entwürfe, `outcome`, `facts`, Kommentare, Dokumente, Angebote, interne Notizen, Absagegründe der Organisator:innen, `created_by/submitted_by/approved_by`, Kontaktadressen, Instagram-CDN-URLs, Hex-Farben, Koordinaten (Stufe C), Revisionsnummern.

### 9.2 Parameter

| Parameter | Regel |
|---|---|
| `from`, `to` | wie M1 (`AwareDatetime`, 422 bei naivem Wert); `from` filtert `ends_at >= from`, `to` filtert `starts_at <= to` |
| `since` | **ISO-8601 mit Offset** (`2026-10-20T09:00:00+02:00` oder `Z`); gefiltert wird `updatedAt >= since`. Ohne Offset oder nach dem Dekodieren kaputt (ein unkodiertes `+` wird zum Leerzeichen) ergibt **400** `invalid_since` mit Hinweis "Offset URL-kodieren: %2B02:00" (Auftrag; die übrigen Parameter bleiben bei 422, 13.1.1). Zukunftswerte sind erlaubt |
| `category` | Slug; trifft Haupt- **und** Elternkategorie (`categories[].slug`), also liefert `fachschaft` alle drei Fachschaften |
| `organization` | Slug der Organisation; `org` bleibt als veralteter Alias (M1), beide verschieden ergibt 422 |
| `limit`, `cursor` | `limit` 1..500, Standard 100; `cursor` ist undurchsichtig (`base64url` über `{startsAt, id}`), Sortierung `startsAt`, `id`; ungültiger Cursor 422 `invalid_cursor`; `nextCursor` ist `null` auf der letzten Seite |

`since` und das Verschwinden: ein Dossier, das den Feed verlässt (T07, Verwerfen), erscheint in `since`-Abfragen nicht als gelöscht; Verbraucher bauen den Bestand mit einer vollen Abfrage neu auf (bekannte Grenze, 13.2 D13). Absagen bleiben als `status: cancelled` im Feed.

### 9.3 Antwortkopf

`Cache-Control: public, max-age=300, stale-while-revalidate=60` (wie M1, ICS dagegen 3600), `ETag` (stark; Hash über Items **und** `nextCursor`, nicht über `generatedAt`), 304 bei `If-None-Match`, `X-Robots-Tag: noindex`, nie `Set-Cookie`, kein CORS. Die Antwort wird aus dem Snapshot (9.5) gefiltert und paginiert; der ETag gilt je Abfrage.

### 9.4 `textHtml` (Sanitizer, M3 12.24)

`public_event_v.description_md` → `markdown-it-py` (CommonMark, `html=False`, Typografie aus) → `nh3.clean` mit Tags `p, a, strong, em, ul, ol, li, br`, Attribut `href` an `a`, Schemata `http, https, mailto`, `rel="noopener noreferrer nofollow"`; Überschriften, Bilder (`/api/media/images/…` ist privat), Tabellen, Code und Roh-HTML verlieren ihre Tags, der Text bleibt. Neue Laufzeit-Abhängigkeiten: `markdown-it-py`, `nh3`; Entwicklungs-Abhängigkeit: `icalendar`. Testfälle: `<script>`, `onerror`, `javascript:`, `data:`, `//evil`, Bild im Text, verschachtelte Listen, Links im Text sind durch E07 (ein neuer Host ist kritisch) bei der Freigabe geprüft, der Sanitizer bleibt trotzdem das zweite Netz. `textHtml` wird nur im Worker-Snapshot und in der Live-Rückfallebene berechnet, nie in der View.

### 9.5 Cache im Worker (`worker/public_cache.py`)

PLAN 8.1: der Worker baut Feed und ICS, Anfragen rechnen nichts. Redis, keine Tabelle (2.7).

- **Schlüssel:** Version `events:feed:version` (bleibt der Zähler aus `pipeline/actions.py`); Snapshots als Redis-Hash `events:public:snap:<name>` mit den Feldern `version`, `etag`, `body`, `contentType`, `generatedAt`, Ablauf 2 Stunden; Namen `feed` (alle öffentlichen Items, JSON, voll), `ics:all`, `ics:k:<slug>` je aktiver Kategorie mit Ereignissen im Fenster plus je Elternkategorie.
- **Bau:** Job `rebuild_public_cache` (arq, `_job_id = "public_cache"` entprellt Mehrfachauslösung; liest `events:feed:version` **vor** dem Lesen der View und schreibt diese Version mit) liest die View über die Rolle `events_public` einmal, berechnet Items, `textHtml` und alle ICS-Texte und schreibt die Snapshots atomar (`MULTI`). Obergrenze 5000 Zeilen; darüber loggt der Job `snapshot_too_large` und die API bleibt bei der Live-Ebene.
- **Auslöser:** (1) Aktion `invalidate_feed_cache` zählt die Version hoch **und** stellt `rebuild_public_cache` ein (T05, T07 wie bisher; neu auch `cancel`, `postpone`, `reinstate`, `confirm-location`, Poster-Austausch `promote_poster`, T08/T08b/T09/T09b, jede Änderung öffentlicher Felder eines `live`-Dossiers über `PATCH`, `save-as-format`, `PUT /events/{id}/format`); (2) Cron stündlich, Minute 5 UTC (das Fenster der ICS und `now` wandern, Fehler heilen).
- **Lesen:** die API nimmt den Snapshot nur, wenn `version` dem aktuellen `events:feed:version` entspricht; sonst (oder bei Redis-Fehler, fehlendem Snapshot, Version älter als 5 Minuten) baut sie live aus der View (Fehler im Snapshot sind nie ein 500) und stellt `rebuild_public_cache` ein. Der Prozess hält den zuletzt gelesenen Snapshot samt ETag im Speicher, bis sich der ETag ändert.
- **Zeit:** `generatedAt` ist die Bauzeit des Snapshots (live: die Anfragezeit); `now` für das ICS-Fenster kommt aus dem Job und ist in Tests injizierbar.
- **Tests:** `test_snapshot_matches_live` (Feed und ICS aus Snapshot und aus der View sind byte-gleich bis auf `generatedAt`), `test_invalidate_rebuilds` (T05 ändert ETag in einer Frist), `test_redis_down_falls_back_live`, `test_stale_version_is_not_served`.

## 10. Kanarienvogel und Leck-Schutz (E39, E41, A06, A07)

### 10.1 Seed (`backend/tests/_support/canary.py`)

Jede nichtöffentliche Stelle trägt eine eigene Zeichenkette `CANARY-INTERNAL-<FELD>` (Großbuchstaben, eindeutig). Ein öffentliches Dossier mit `CANARY-PUBLIC-TITLE` im Titel, `CANARY-PUBLIC-SUMMARY` im Kurztext und einem Ort stellt den Positiv-Beweis (der Test beweist, dass er öffentliche Strings findet, sonst wäre ein leerer Feed "sauber").

| Stelle | Kanarien-Feld |
|---|---|
| Anhang `visibility = team` und `org` (Anzeigename, Alt-Text, Credit, Quelle) | `TEAMFILE`, `ORGFILE`, `ALTTEXT`, `CREDITSOURCE` |
| Anhang `visibility = shared`, aber `scan_status = pending` und `infected` | `SHAREDPENDING`, `SHAREDINFECTED` |
| Dokumente `team`, `org`, Rückblick, Notiz, Mailvorlage (Titel und Rumpf) | `DOCTEAM`, `DOCORG`, `RETRO`, `NOTE`, `MAILTPL` |
| Kommentare (Wurzel und Antwort) | `COMMENT`, `REPLY` |
| Vergleichsangebote (Anbieter, Notiz, Betrag 987 654 ct), Businessplan, Vertrag | `QUOTEVENDOR`, `QUOTENOTE`, `BUSINESSPLAN`, `CONTRACT`; Betrag als Ziffernfolge `987654` |
| Interne Notizen: `image_exception.reason`, Absage-Freitext der Organisator:innen (`event_status_event.note`), Revisionsnotiz, `change_note`, Checklistenpunkt, `waived_reason`, `outcome.notes`, `waivedReason`, `facts` (Freitextfelder), Benachrichtigungs-`params` | `EXCEPTION`, `CANCELNOTE`, `REVNOTE`, `CHECKLIST`, `WAIVED`, `OUTCOMENOTES`, `FACTS`, `NOTIFPARAM` |
| Privatadresse: `venue.address`, `venue.postcode`, `venue.notes` eines `is_private`-Orts; Adresse eines nicht privaten Ortes mit `public_precision = hidden`; freier `venue_text` ohne Bestätigung | `PRIVATEADDRESS`, `HIDDENADDRESS`, `UNCONFIRMEDTEXT` |
| Personen: `created_by`, `submitted_by`, `approved_by` (OIDC-`sub` mit Kanarien-Suffix), Organisations-`contact_public` | `SUBCREATOR`, `SUBAPPROVER`, `CONTACT` |
| Entwurf im Zustand `idea`, `planning`, `in_review`, `approved` (Titel), `withdrawn` | `DRAFTIDEA` … `WITHDRAWN` |

### 10.2 Test (`tests/integration/publicapi/test_canary.py`)

Als **Anonym** (kein Cookie, keine Header) werden geladen und als Rohbytes nach `CANARY-INTERNAL-` und nach der Ziffernfolge des Betrags durchsucht: der Feed vollständig (alle Seiten über `nextCursor`, dazu `?since=0001-01-01T00:00:00Z`, `?category=` für jede Kategorie, `?organization=`), jede ICS (`all` und jede Kategorie, inklusive der 404-Antwort), die Medienroute, `GET /api/public/feed/events` mit manipulierten Parametern (Fehlerantworten), sowie `/api/search`, `/api/archive/{id}`, `/api/library`, `/api/templates` (je 401 oder 404, der Rumpf des Fehlers wird mitgeprüft). Als **angemeldete Personen** laufen dieselben Prüfungen für `member`, `organizer-makers` (fremde Organisation) und `viewer` auf Archiv, Bibliothek, Suche, Vorlagen und Klon-Vorschau: gefunden werden darf höchstens der Kanarienvogel der Felder, die laut 4.1 für fremde Organisationen lesbar sind (`shared`-Dokument, Kerndaten), nie `TEAMFILE`, `ORGFILE`, `QUOTE*`, `OUTCOMENOTES`, `COMMENT` und die Ziffernfolge. Gegenprobe: `organizer-fsi` findet seine eigenen `org`-Strings in Suche und Klon-Vorschau (damit der Test nicht deshalb grün ist, weil nichts gefunden wird). Zusätzlich `test_canary_freedom_after_each_transition` (die Prüfung läuft nach T04, T05, `cancel`, T08, T09), und `test_every_state_reaches_the_view_only_when_allowed`.

### 10.3 Allowlist-Lint (E39)

`backend/app/modules/publicapi/allowlist.py` führt `PUBLIC_FIELDS: Mapping[str, frozenset[str]]` (Modell → erlaubte Felder, rekursiv) und `PUBLIC_VIEW_COLUMNS`. Tests (`tests/unit/publicapi/test_public_allowlist.py`): (1) jedes Pydantic-Modell in `publicapi/schemas.py` und jede Klasse, die der ICS-Schreiber liest, hat genau die Felder der Allowlist; ein neues Feld lässt den Test bis zur Allowlist-Änderung (CODEOWNERS-Eintrag, Review) scheitern; (2) `PUBLIC_EVENT_V` in `publicapi/service.py` stimmt mit `PUBLIC_VIEW_COLUMNS` und (Integration) mit `information_schema.columns` der View überein; (3) AST-Lint über **alle** Dateien unter `publicapi/` mit `rglob` (der M1-Lint nutzt `glob` und verfehlt Unterpakete): kein `model_dump`, `model_validate`, `from_attributes`, `.dict(`, kein Import von `app.modules.*.models`, `app.db.get_session`, `Event`, `Attachment`; (4) `events_public` kann außer den Views nichts lesen (Integration: `SELECT` auf `event`, `document`, `attachment`, `format`, `venue` ergibt `permission denied`).

### 10.4 Schemathesis und Vertrag

`tests/integration/publicapi/test_schemathesis.py` (Schemathesis 4.30.1, aus `/openapi.json` der App, eingeschränkt auf `/api/public/*` und `/ics/*`): alle Standardprüfungen (`not_a_server_error`, `status_code_conformance`, `content_type_conformance`, `response_schema_conformance`, `response_headers_conformance`), `max_examples=200` mit negativen Fällen, dazu eine eigene Prüfung "Antwort erfüllt `feed-v2.json`" (`jsonschema_rs`) und "kein `Set-Cookie`, kein `Access-Control-Allow-Origin`". `test_openapi_matches_feed_v2` stellt sicher, dass die Pydantic-Modelle und die JSON-Schema-Datei dieselben Felder und Pflichtfelder nennen. Läuft gegen Postgres (Testcontainers) mit der Rolle `events_public`, mit Beispielen aus der Kanarien-Seed.

## 11. Frontend

Alle Screens folgen PLAN 15.1 Wort für Wort (Elemente, Zustände, Leer, Fehler, Komponenten); dieser Abschnitt hält die Verdrahtung fest. Standalone, OnPush, Signals, separate `.html`/`.scss`, Texte in `i18n/de` (gegendert mit Doppelpunkt oder neutral), Kit-Tokens, Hell und Dunkel, 360 px ohne horizontales Scrollen, axe grün, Tastaturpfade. Neue Übersetzungsdateien `translations.archive.de.ts` (Archiv, Suche, Palette, Bibliothek), `translations.format.de.ts`, `translations.calendar.de.ts`; neue Texte der Nachbereitung in `translations.dossier.de.ts`. Alle neuen Bereiche laden lazy; das Initial-Bundle (612,95 kB am Ende von M4, Budget 1,1 MB) wächst nicht (der Bundle-Test aus M4 wird um die neuen Pfade erweitert).

### 11.1 Routen und Navigation

| Route | Inhalt |
|---|---|
| `/dossiers/neu?vorlage=<id>` | I06 als Dialog über der Liste (Reiter "Neu" und "Aus Vorlage" in I05) |
| `/dossiers/:id/nachbereitung` | neuer Reiter (Voreinstellung D11), sichtbar bei `live` nach Ende, `followup`, `archived` |
| `/kalender` | interner Kalender (7) |
| `/archiv` | I20 (Standardfilter `state=archived`, Query-Parameter `q, scope, state, org, year, category, format`) |
| `/formate`, `/formate/:slug` | I18 |
| `/bibliothek`, `/bibliothek/:kind/:id` | I19 |

Rail (`app-nav-rail`): Aufgaben, Pipeline, Dossiers, **Kalender, Archiv, Formate, Bibliothek**, Verwaltung, Konto. Bottom-Bar (Handy, vier Plätze): Aufgaben, Pipeline, Kalender, Archiv (PLAN 15.0 nennt als vierten Platz "Eingang", der erst mit M6 existiert); "Mehr" (`app-side-sheet`): Formate, Bibliothek, Verwaltung, Konto. Rechtefilter in `nav.service.ts` bleibt Bequemlichkeit.

### 11.2 I06 Neu aus Vorlage (`features/dossiers/clone/`)

`app-dialog` mit `app-search-pill` (live, 250 ms) über `GET /api/templates`, Filter Format, Kategorie, Jahr (`app-filter-select`), Trefferliste (`app-list-item`: Titel, Datum der Ausgabe, Organisation, "Anleitung geprüft am 12.02.2026" oder "Anleitung ungeprüft" als Warntext). Rechts die Vorschau "Was wird übernommen" aus `GET …/clone-preview` mit `app-config-diff` (übernommen, nicht übernommen mit Grund, z. B. "Poster: Datum im Bild, bitte neu gestalten"), darunter "Letztes Mal" (Besucher:innen, Kosten; fremde Organisation: Hinweis "Angebote und Businesspläne bleiben bei der ursprünglichen Organisation.") und, bei eigener Organisation, "Angebote der letzten Auflage" (`app-quote-table`, nur wenn die Anfrage 200 liefert). Felder: Organisation (nur wenn mehrere), neuer Beginn (`app-datetime-zone`), optional Ende, Titel. Knopf "Neu anlegen" führt zum neuen Dossier. Zustände: Laden (`app-skeleton`), leer "Keine passende Vorlage gefunden. Versuch es mit einem anderen Begriff oder leg das Event neu an.", Fehler "Vorlage nicht mehr verfügbar." (409/404) und "Neues Datum fehlt.". Auf dem Handy Bottom-Sheet mit Liste, dann Vorschau als zweiter Schritt.

### 11.3 I18 Format (`features/formats/`)

`/formate`: `app-list-detail`, Suche, Zeile mit Titel, Organisation, "Anleitung geprüft am …" oder Warnung (`howtoStale`, Warnfarbe als Text). `/formate/:slug`: `app-page-header` (Titel, Organisation, Beschreibung), `app-tabs` **Anleitung** (Master-Anleitung im `dossier-markdown-editor`, "Zuletzt geprüft von … am …", Knopf "Als geprüft markieren", Hinweis "Bitte keine privaten Telefonnummern oder Adressen."), **Ausgaben** (`app-data-table`: Datum, Zustand als Text, Besucher:innen, Kosten Ist, "Anleitung ungeprüft"; fremde Ausgaben ohne Kosten), **Checkliste und Mails** (Vorlage des Profils lesend, Verweise auf Mailvorlagen der jüngsten Ausgabe), Kennzahlen-Karte "Letztes Mal" (`app-card`), Knopf "Neue Ausgabe" (öffnet I06 mit dem Format vorgewählt oder ruft `new-edition`). Leer: "Noch keine Ausgabe dieses Formats. [Neue Ausgabe]". Bearbeiten nur mit Recht (`PATCH`/`PUT` antworten 403; die Oberfläche zeigt Felder dann schreibgeschützt). Im Dossierkopf der Menüpunkt "Als Format speichern" (Dialog: Slug, Titel).

### 11.4 I19 Bibliothek, I20 Archiv und Suche

I19 (`features/library/`): `app-list-detail`, `app-search-pill`, `app-filter-select` (Kategorie, Organisation, Jahr, Art), Liste der `LibraryItem`, Detail mit `markdown-view` (Dokumente) bzw. Dateikarte (Anhänge, Download über den Archivpfad, `app-image-thumb` für Bilder), Knopf "In Dossier übernehmen" (Auswahl eines eigenen, offenen Dossiers). Leer wie PLAN. I20 (`features/archive/`): Suchfeld (live, 250 ms), Umschalter **Dossiers | Dokumente | Formate** (`app-segmented`), Facetten als `app-filter-select` mit Zählern, Treffer mit Segment-Hervorhebung, Prüfdatum und Warntext, Aktionen je Treffer ("Öffnen", "Neu aus Vorlage"); Leer: vor der Suche "Suche nach Titel, Ort, Anleitung …", ohne Treffer "Nichts gefunden für „Kinabnd“. Meintest du „Kinoabend“?" (`suggestion`); Fehler "Suchbegriff zu lang (höchstens 100 Zeichen)." (Eingabe mit `maxlength=100` und Servermeldung). Hervorhebung ausschließlich über Segmente (`<mark>` aus Text), kein `innerHTML`.

### 11.5 Palette, Kalender-Grid, Nachbereitung

- **Palette** (`layout/palette/`): Verhalten nach 6.3; `app-command-palette` im Rahmen `rail`, Shortcut-Dienst (Strg/Cmd+K, nicht in Eingabefeldern, die Strg+K selbst brauchen), Gruppen Dossiers, Formate, Aktionen, Navigation, Fokus kehrt beim Schließen zurück.
- **`app-calendar-grid`** nach Abschnitt 7; Page `/kalender` mit Zeitraumwahl (Vor/Zurück/Heute), Modus (Monat/Woche; Handy nur Agenda), Filtern aus M3 (`features/pipeline/filters`).
- **Nachbereitung** (`features/dossiers/followup/`): Kopf "Nachbereitung" mit `app-guard-list` für T09 und dem Übergangsknopf (Dialog I13); Rückblick (`dossier-markdown-editor`, legt das Dokument beim ersten Speichern an, Autosave wie M4); Ergebnis (Besucher:innen, Kosten Ist, Einnahmen, Notiz, Schalter "verzichtet" mit Pflichtfeld Grund, Speichern mit `If-Match`); Häkchen "Anleitung geprüft" (`app-checkbox`, ruft `verify-howto`, zeigt "geprüft von … am …"); Checkliste Phase `followup` als Verweis auf den Reiter. Texte: "Verzicht braucht einen Grund." und die Guard-Meldungen. Dossierübersicht zeigt den Block "Letztes Mal" und das Panel "Aus der Vorlage" (über `derivedFromId`).
- **Orte:** Dialog "Ort ist öffentlich?" (`confirm-location`) am Guard `location_unconfirmed`; Reiter Übersicht bekommt das Feld "Rahmen" (`facts`) mit Profil nach Kategorie (Frontend-Stub `facts.budgetCents` aus M4 wird verdrahtet).

### 11.6 Typen, API-Client, Tests

Typen in `features/{dossiers,formats,archive,library,calendar}/model/` spiegeln Abschnitte 3 bis 7 von Hand (camelCase, `extra=forbid` verlangt exakte Bodies). Jest je Screen (leer, Laden, Fehler, 409/404, Rechte), `calendar-grid` (Tastatur, Mehrtägiges, Agenda unter 768 px, "+n", Token-Uhr), `command-palette` (Fokusfalle, Tastatur, Verwerfen alter Antworten), Segment-Hervorhebung ohne `innerHTML` (Contract-Spec bleibt), `clone-preview`-Darstellung (Tabelle 4.2 als Daten), `bundle-initial`. Playwright `frontend/e2e/m5.spec.ts` (Browser über `nix build nixpkgs#playwright-driver.browsers`): Klon aus der Vorlage mit Vorschau, Format-Seite, Suche und Palette, Kalender (Desktop und 360 px), Nachbereitung bis T09, Bibliothek, Hell/Dunkel, axe.

## 12. Tests

Schwellen und Gates wie M4 (Backend: `ruff`, `basedpyright`, Unit, Integration; Frontend: `lint`, `typecheck`, Jest 97/94/97/98, `build`). Neu in M5: das Gesamt-Gate steigt von 90 % auf **97 %** (Zusage in M2/M3; `fail_under` in `pyproject.toml`, M4 stand bei 98 %); `scripts/coverage_critical.py` verlangt 100 % Branch zusätzlich für die Pakete `archive` und `search` und für `formats/service.py` (`publicapi` einschließlich `ics/` und `worker/public_cache.py` steht schon auf der Liste). Neue Einstellungen (`ICS_UID_DOMAIN`, `PUBLIC_SNAPSHOT_MAX_AGE_SECONDS`, `PUBLIC_SNAPSHOT_MAX_ROWS`) stehen in `.env.example` (`test_env_example_settings_parity`). Kopien aus dem Upstream (Kalender- und Palette-Gerüst) bekommen Kopfzeile und `PROVENANCE.json`-Eintrag (`test_provenance`). Mails: Integrationstests laufen mit Redis und `CapturingMailSender`.

### 12.1 Backend, Unit

`test_carry_over_table` (jede Zeile von 4.2 × {eigene, fremde Organisation}, das Orakel ist die Tabelle selbst) · `test_strip_edition` ("Movienight WS26/27", "Campusfest 2026", "Movienight: Whiplash" bleibt) · `test_clone_dates` (Dauer der Vorlage, ganztägig, Sommer-/Winterzeit) · `test_clone_due_offsets` (Ableitung aus einem von Hand gesetzten `due_at`, Begrenzung ±365) · `test_outcome_model` (Grenzen, `waived` löscht Zahlen, Grund >= 10) · `test_guards_t09_truth_table` (alle 16 Kombinationen aus Rückblick, Ergebnis, Prüfung, Checkliste; "nichts zu prüfen") · `test_snapshot_builders_set_m5_fields` · `test_pipeline_matrix_m5` (Vollmatrix wächst um T08 bis T10 mit echten Guards, 100 % Branch bleibt) · `test_location_guard` · `test_facts_profiles` · `test_all_day_times` (Tage mit 23 und 25 Stunden, `starts_on/ends_on`) · `test_search_query_builder` (jeder Wert gebunden, `%`/`_`/Anführungszeichen, Rechteklausel immer vorhanden, Trigramm je Wort) · `test_translit` · `test_search_segments` (Steuerzeichen werden zu Segmenten, HTML bleibt Text) · `test_archive_readable_truth_table` (Rolle × Beziehung × Sichtbarkeit × Art × Scanstatus) · `test_calendar_range` (100 Tage, Ortsdaten, Überschneidung, Mitternacht) · `test_feed_cursor` · `test_feed_since` (`Z`, Offset, Leerzeichen-Fall 400) · `test_text_html_sanitizer` (9.4) · ICS: `test_ics_fold`, `test_ics_escape`, `test_ics_text_never_injects` (hypothesis), `test_vtimezone_matches_zoneinfo`, `test_ics_dst_fold`, `test_ics_goldens` (8.6), `test_ics_uid_domain_is_pinned`, `test_ics_order_is_deterministic` · `test_public_allowlist` (10.3) · `test_category_depth` · `test_route_authz_inventory` (alle neuen Routen in `ROUTE_PERMS`, öffentliches Präfix `/ics/`) · `test_camel_case_contract` (neue Modelle) · `test_kinds_m5` (neun Kinds, Essenzielle unverändert).

### 12.2 Backend, Integration (`pytest -m integration`, Docker, Redis, MinIO, Postgres)

`test_migrations` (frische DB gleich Upgrade von 0005 mit Bestandszeilen aller Zustände; Datenschritt Ort, Steuerzeichen-Bereinigung, `document`-Besitz-CHECK) · `test_db_grants` (kein `DELETE` auf `format`; `events_public` liest nur Views) · `test_public_view_columns` · `test_view_location_rules` (private Orte, `hidden`/`building`/`exact`, freier Ortstext mit und ohne Bestätigung) · `test_t09_*` (Guards, Format-Hook, Rollenmatrix, 409 bei Zustand) · `test_t09b_marker_and_mail` · `test_followup_reminder_once` (genau eine Mail je Eintritt, T10 öffnet einen neuen) · `test_verify_howto_archived` · `test_clone_movienight_own_and_foreign` (12.3 a) · `test_clone_preview_equals_report` · `test_clone_is_atomic` (Fehler beim Kopieren der Checkliste rollt alles zurück) · `test_clone_never_copies_files` (Speicher: keine neue Objektdatei) · `test_archive_read_matrix` (Rolle × {eigene, fremde, ohne Organisation} × Route, Soll 200/404) · `test_attachment_download_foreign_shared` · `test_library_visibility` · `test_formats_api` und `test_formats_rbac` · `test_save_as_format` · `test_new_edition` · `test_search_20` (liest `queries.yaml`) · `test_search_total_equals_walked_hits` · `test_search_timeout` · `test_calendar_view` · `test_all_day_event_api` · `test_confirm_location_blocks_t04` · `test_facts_api` · `test_feed_v2` (Felder, Cursor, `since`, Filter, Eltern-Kategorie) · `test_snapshot_*` (9.5) · `test_ics_routes` (Header, ETag, 304, kein Cookie, 404) · `test_canary` (10.2) · `test_schemathesis` (10.4) · `test_rbac_matrix` (Rolle × Organisation × alle neuen Routen) · `test_poster_promote_rebuilds_cache`.

### 12.3 Abnahme M5 (wörtlich, PLAN §16.1 Zeile M5, Spalte "Fertig wenn …")

> Movienight-Fixture: aus archivierter Ausgabe entsteht ein Dossier ohne Poster, Ausnahme und Angebote, Checkliste neu gerechnet, "Letztes Mal" zeigt Besucher:innen und Kosten; Archivsuche besteht die 20 Mustersuchen ("Fachschaftssitzung" findet "Sitzung"); ICS-Golden-Tests grün und in Google, Apple, Thunderbird importiert; Kanarienvogel findet in JSON, ICS nichts Internes; Schemathesis gegen Feed grün

`backend/scripts/m5_acceptance.py` (Muster `m4_acceptance.py`, gegen den Dev-Stack, nie gegen Live; Zeit über die Muster von `m3_worker.py`/`m4_ops.py` gesetzt) prüft in dieser Reihenfolge und schreibt `docs/M5-ABNAHME.md`. Fixture: `backend/tests/fixtures/movienight.yaml` mit den **23** Kopien des Bestands (KARTE 2.7: WS25/26 = 8, SoSe26 = 8, WS26/27 = 7 mit dem Halloween-Doppel; Wochentage Di 7, Do 5, Fr 5, Mo 4, Mi 2), als `archived` die acht Ausgaben WS25/26, Format `movienight`, Organisation `fsi`, Kategorie `kino`; WS26/27 hängt am Semesterposter 1440×1800 (ein Bild an sieben Dossiers). Titel der Filme, Termine, Besucherzahlen und Beträge sind **synthetisch** (nur die Muster "STUPA Movienight: <Film> (OmU)" und "<Film> – STUPA Movienight" stammen aus KARTE 2.7); eine Ausgabe trägt Poster, `image_exception`, zwei Angebotsgruppen mit Beträgen, Kommentare, eine vollständig abgehakte Checkliste mit Zuständigen, Anleitung, Mailvorlage, Notiz, Rückblick und `outcome {attendance: 87, costsCents: 24500, revenueCents: 13000}`.

| # | Prüfpunkt | Beleg |
|---|---|---|
| a | Klon der Ausgabe durch `organizer-fsi`: Dossier in `idea` mit `derivedFromId`; `poster` und `imageException` leer, `GET /quotes` leer, keine Anhänge, keine Kommentare; Checkliste mit allen Punkten offen, ohne Zuständige, `dueAt` aus dem neuen Beginn (`checklistRecomputed = n`, Stichproben −28/−7/+7 Tage); Notiz und Mailvorlage kopiert (Revision 1), Anleitung als Link auf das Format; `lastTime` zeigt 87 Besucher:innen und 245,00 € Kosten; Panel "Angebote der letzten Auflage" 200 für FSI; Vorschau gleich Bericht. Dieselbe Vorlage durch `organizer-makers`: nur das Archiv (`archived`) klonbar, `lastTime` mit Besucher:innen, ohne Kosten, `restricted = true`, nur `shared`-Dokumente kopiert, Panel 404, fremde `live`-Ausgabe 404 | HTTP + DB |
| b | die 20 Mustersuchen aus `queries.yaml` (6.4) als die dort genannten Konten; Soll gleich Ist je Zeile, Trefferzahlen im Protokoll; "Fachschaftssitzung" findet "Sitzung" | HTTP |
| c | ICS-Golden-Dateien (8.6) byte-gleich; jede Datei mit `icalendar` lesbar; Feed-`/ics/all.ics` und `/ics/k/<slug>.ics` der Dev-Daten gegen die Eigenschaften; **Import in Thunderbird** am Entwicklungsrechner (Thunderbird ist im Profil vorhanden; Kalender "Lokal", Datei- und URL-Abo gegen `http://localhost:8081`): Termine, Absage (durchgestrichen oder als abgesagt markiert), Verschiebung und die Umstellung 25.10.2026 werden als Screenshot-Protokoll ohne personenbezogene Daten festgehalten. Google (Import einer Datei im Web-Kalender) und Apple (Kalender-App, Abo-URL) sind **nur als Schrittfolge dokumentiert und manuell** abzunehmen, weil sie eine öffentliche HTTPS-Adresse beziehungsweise ein Gerät brauchen, das hier fehlt; das Protokoll trägt sie als "nicht geprüft", bis Luis sie bestätigt | Golden + manuell |
| d | Kanarienvogel (10.2): Feed, jede ICS, Suche, Archiv, Bibliothek, Vorlagen als Anonym und als `member`/`organizer-makers`/`viewer`: kein `CANARY-INTERNAL-` und keine Betragsziffern; Positiv-Kanarienvogel wird gefunden | HTTP |
| e | Schemathesis gegen `/api/public/*` und `/ics/*` plus `feed-v2.json`: 0 Fehlschläge, `max_examples=200` | pytest |
| f | Feed-Cache: T05 eines Dossiers, `rebuild_public_cache` läuft, neuer ETag in der Frist, 304 mit altem ETag nicht mehr, Antwort aus dem Snapshot (`X-Cache`-freies Prüfen über Redis-Schlüssel); Redis angehalten: Feed und ICS antworten live aus der View, kein 500; Redis an: Snapshot kehrt zurück | HTTP + Redis |
| g | Nachbereitung mit gesetzter Uhr: T08 nach Ende + 12 h; nach 7 Tagen genau eine Erinnerung (Mail mit `CapturingMailSender`, zweiter Lauf 0); T09 bei fehlendem Rückblick/Ergebnis/Prüfung 422 mit `reasons[]`, dann nach Eingabe 200, `format.last_verified_at` gesetzt, Master-Anleitung geprüft; zweites Dossier ohne Eingabe: T09b nach 30 Tagen, Kennzeichen "Anleitung ungeprüft", Mail `auto_archived`, Format unberührt; `verify-howto` in `archived` löst das Kennzeichen und berührt das Format; T10 öffnet neu | HTTP + Log |
| h | Kalender: `view=calendar` für Oktober 2026 (Randtage), mehrtägiger Eintrag, Halloween-Doppel, ganztägiger Termin, 101 Tage ergibt 422; Sichtbarkeit fremder Organisation | HTTP |
| i | Archiv-Lesen und Bibliothek: `member` sieht Kerndaten und `shared`-Dokumente archivierter Dossiers, `team`/`org` nicht; Download eines fremden `shared`-Anhangs 200, eines `org`-Anhangs 404, eines `pending` 409 nicht erreichbar (nicht gelistet); `adopt` kopiert nur Text | HTTP |
| j | Ort und Rahmen: T04 mit freiem `venue_text` ohne Bestätigung 422 `location_unconfirmed`; `confirm-location`, dann T04 200, View und Feed zeigen den Ort; Party ohne `ageLimit` blockt T02; ganztägiger Termin anlegen, im Feed (`startsOn/endsOn`) und im ICS (`VALUE=DATE`) | HTTP |
| k | Sequenz PLAN 4.6 durchgespielt: Suche → Klon → Poster → T01, T02 → Rückfrage und T03 → Ersetzen → T02 → T04 → T05 → Eintrag in Feed **und** ICS | HTTP |
| l | Browser (Playwright, 360 px und Desktop, Hell und Dunkel, axe): I06, I18, I19, I20, Palette, Kalender, Nachbereitung; Tastaturpfade für Palette, Kalender und Klon | Playwright |
| m | `deploy/backup.sh` gegen den Dev-Stack mit Migration 0006, `deploy/restore-smoke.sh` grün (Revision `0006_archive_feed`, Zeilenzahlen gleich) | Skript |

Das Protokoll listet außerdem die offenen Punkte aus `M4-ABNAHME.md` "Offen", die M5 berührt (Platzhalter `facts`, Standort-Bestätigung, Nachbereitungsfelder jetzt echt; Frontend-Stubs `facts.budgetCents` und "Als Vorlage für das Format speichern" verdrahtet; Status-Texte der Anhangsliste unverändert).

### 12.4 Meilenstein A-I (Pilot `v0.1.0`)

PLAN §16.1: "mindestens eine echte Veranstaltung durchläuft Idee bis Archiv im System, mindestens 10 echte kommende Events mit Bild stehen im Feed, `restore-smoke` grün, Pilot-Feedback als Issues erfasst". M5 beweist nur den technischen Teil; die echten Veranstaltungen und das Feedback kommen von der Redaktion, FSI und MAKERS und lassen sich nicht aus dem Repo prüfen.

| Kriterium | Wer | Beitrag von M5 | Beleg |
|---|---|---|---|
| Eine echte Veranstaltung Idee → Archiv | Redaktion, FSI, MAKERS (Luis ordnet an) | alle Übergänge T00 bis T09, Klon, Nachbereitung, Feed und ICS laufen; Akzeptanz k und g im Dev-Stack | Pilotprotokoll (nicht M5) |
| >= 10 echte kommende Events mit Bild im Feed | Redaktion | Feed/ICS aus Snapshot, `venue` und Ort-Bestätigung, Poster-Pflicht (E41); Skript `scripts/pilot_check.py` zählt öffentliche Events mit Poster der Ziel-Instanz (nur lesend über den Feed) | Zahl im Pilotprotokoll |
| `restore-smoke` grün | Technik | `deploy/restore-smoke.sh` läuft gegen ein Backup mit Migration 0006 (12.3 m); **neuer CI-Job `restore-smoke`** in `.github/workflows/ci.yml` (Postgres-Container, kleines Seed-Backup mit `age`-Testschlüssel, ohne MinIO), Pflicht vor jedem Tag `v*` (E26) | Lauf lokal + CI-Job |
| Pilot-Feedback als Issues | Redaktion | Vorlage `.github/ISSUE_TEMPLATE/pilot-feedback.md` | Issues |

Der Tag `v0.1.0` entsteht erst nach Okay von Luis; M5 pusht und deployt nichts (`deploy/deploy.sh` bleibt Dokumentation).

## 13. Abweichungen und offene Entscheidungen

### 13.1 Abweichungen vom PLAN und von M1 bis M4 (zur Nachführung durch Luis)

1. **Feld- und Parameternamen:** `categories[].kind` statt Auftrag und ENTWURF `type` (M1, Kategorie-API und `feed-v2.json` nutzen `kind`); `organization` behält `id` (additiv); Parameter `organization` ist kanonisch, `org` bleibt Alias; `since` (Auftrag) statt PLAN `changedSince`; `since` ohne gültigen Offset ergibt 400, `from`/`to` bleiben bei 422 (M1-Test); Hülle bleibt `items[]` und englisch (M1 10.1.1), PLAN 8.2 zieht nach; Feed trägt zusätzlich `startsOn, endsOn, ticketUrl, websiteUrl, costText, textHtml` (PLAN 8.2, D2).
2. **ICS:** Pfad `/ics/k/<slug>.ics` statt PLAN `/ics/c/<slug>.ics`; `VTIMEZONE` und `TZID` statt "alle Zeiten UTC, kein VTIMEZONE" (PLAN 8.3, Auftrag gewinnt); die wiederholte Stunde der Umstellung wird als `Z` ausgegeben (D8); `X-PUBLISHED-TTL`/`REFRESH-INTERVAL` `PT1H` und `max-age=3600` statt PT12H und 300; Router außerhalb von `/api`; Middleware, Inventur und nginx kennen `/ics/`.
3. **Wissensebenen:** Rückblick als Dokument `retrospective` statt Spalte `retrospective_md` (PLAN 3.3 listet beides; M4 10.1.9 hatte die Wahl offengelassen); `document.event_id` wird nullable mit `format_id` (nur `howto`), **keine** `owner_kind = library` und keine Format-eigenen Checklisten und Mailvorlagen (PLAN 7.3 Ebenen 1 und 3, 3.3 `checklist` mit `owner format`): die Bibliothek ist eine Sicht auf geteilte, archivierte Inhalte, die Formatseite zeigt die Vorlage des Profils und die Mailvorlagen der jüngsten Ausgabe; `library.manage` bleibt ungenutzt.
4. **JSON-Schlüssel** in `outcome`, `facts`, `defaults` sind camelCase wie `attachment.meta` (M4); der Auftrag schreibt `costs_cents`, PLAN 3.4 `budget_cents`.
5. **`format`** hat `title` statt PLAN `name`, `defaults` (JSONB) statt `default_category_ids` und `default_checklist_template_id` (Auftrag), zusätzlich `description_md` und `active`.
6. **`format.last_verified_at`** wird in der Transaktion von T09 gesetzt, nicht als Aktion nach dem Commit (PLAN 4.3): ein Fehler kann so nicht still ausfallen.
7. **Palette** hat vier Gruppen (Dossiers, Formate, Aktionen, Navigation, Auftrag) statt der sechs aus PLAN I20 (Events, Dokumente, Formate, Orte, Organisationen, Seiten); die Archivseite hat die Facetten Format, Kategorie, Organisation, Jahr, Zustand, aber **nicht** "hat Checkliste" und "hat Vergleichsangebote" (die zweite bräuchte eine zusätzliche Rechteprüfung der Beträge, die erste hat keinen Nutzen ohne Vorlagenfilter).
8. **Vorlagen-Suche** sortiert nach Relevanz, Prüfdatum, Datum (PLAN: "nach Format, Relevanz, `last_verified_at`"); die Gruppierung nach Format macht der Client.
9. **Social-Post-Texte** werden nicht geklont (PLAN 7.4 "ja, als Entwurf ohne Bild"): M4 speichert sie nur an Bilddateien; ohne Datei gibt es keinen Entwurf. Die Texte bleiben über das Panel "Aus der Vorlage" erreichbar.
10. **Klon-Felder, die der PLAN nicht nennt:** `cost_text` wird übernommen (öffentlicher Text, kein Link), `website_url` nicht (Link-Host, E07), `venue_text` wird übernommen, die Bestätigung fällt weg.
11. **Format-Stammdaten ohne `If-Match`** (letzter Schreiber gewinnt, Audit), wie Anhangsmetadaten (M4 10.1.6); Dokumente (Master-Anleitung) behalten ETag und Pflicht-`If-Match`.
12. **`location_precision` jetzt, ohne `geo_override`, `lat`, `lon`:** M1-Abweichung 4 wird zur Hälfte aufgelöst (Textbestätigung, Guard, View); Koordinaten bleiben Stufe C. `public_archive` und der Legacy-Filter der View kommen mit M6.
13. **T07 (Offline nehmen)** erzeugt im ICS kein `STATUS:CANCELLED`: die Zeile verlässt die View. Wer einen Termin ankündigen und zurückziehen will, nutzt `cancel` (bleibt im Feed als `cancelled`). Dasselbe gilt für `since`.
14. **Archivlesen** über eigene Pfade (`/archive/{id}`, erweiterte Dokument- und Anhangsrouten); `load_visible` und die M3/M4-Routen bleiben 404 für fremde Organisationen (löst M4 10.1.8).
15. **Bestandstests und Skripte ändern sich:** der Test `item["venueText"] == "Kinosaal 9-133"` bleibt gültig, aber jedes Dossier mit freiem `venue_text` braucht vor T04 `confirm-location`; `m1_acceptance` bis `m4_acceptance`, die Fabriken in `tests/integration/events/harness.py`, `scripts/seed_dev.py` und `e2e/m1..m4.spec.ts` rufen es auf (wie M4 10.1.23).
16. **PLAN §18 Minor 2 und 3:** der Auftrag ordnet beide dem Feed zu. Minor 3 (Mitveranstalter) berührt ihn (`organization` ist nur die Hauptorganisation; `event_organization` gibt es nicht); Minor 2 (Antwortzeit beim Abo) gehört zu `subscribe` in B3 und hat im Feed keinen Gegenstand. Beide bleiben offen (13.2 D12); Minor 4 (EXIF) erledigte M4.
17. **Die Zeile "Google, Apple, Thunderbird importiert"** der Abnahme wird für Thunderbird lokal geprüft, für Google und Apple als Schrittfolge dokumentiert (12.3 c, D16).
18. **Wiederholte Stunde, beide Durchläufe in UTC** (Integrationslauf): ical.js 2.2.1, der Parser von Thunderbird, liest `DTSTART;TZID=Europe/Berlin:20261025T023000` als 01:30Z (zweiter Durchlauf) statt 00:30Z; D8 nahm das Gegenteil an. Der Schreiber gibt deshalb jeden Instant der wiederholten Stunde in UTC aus (`timezone.ambiguous_instant`), Golden `dst-2026-10-25.ics` nachgezogen.

### 13.2 Entscheidungen für Luis (Vorschläge, nicht belegt)

- **D1 Bestehende öffentliche Dossiers mit freiem Ortstext** (Datenschritt 2.2): **bekommen `building` und eine System-Bestätigung**, damit der Ort im Feed bleibt. Alternative: `hidden`, die Redaktion bestätigt jeden Ort nach (sicherer, aber der Ort verschwindet zunächst).
- **D2 Feldumfang des Feeds:** **`startsOn/endsOn`, `ticketUrl`, `websiteUrl`, `costText`, `textHtml` aufnehmen** (alles Text-Klasse, öffentlich gewollt, PLAN 8.2). Alternative: erst mit dem Astro-Loader.
- **D3 Klon aus fremder Organisation:** **nur Checklistenpunkte aus der Vorlage**, keine freien Punkte (sie können interne Namen enthalten). Alternative: alle Punkte ohne Zuständige.
- **D4 "Ergebnis eingetragen":** **`attendance` und `costsCents` (0 erlaubt)** oder ausdrücklicher Verzicht. Alternative: `attendance` genügt. Die Formate-Seeds (Organisation je Format, 2.1) sind Startvorschlag.
- **D5 Anleitung geprüft bei Dossiers ohne Anleitung:** **erfüllt** ("nichts zu prüfen"). Alternative: T09 verlangt immer eine Anleitung.
- **D6 Rückblick:** **nicht leer genügt**. Alternative: Mindestlänge (z. B. 100 Zeichen).
- **D7 `postponed` im ICS:** **`STATUS:TENTATIVE`** plus Zeile "Verschoben: …". Alternative: `CONFIRMED` mit neuem Datum und nur der Zeile.
- **D8 Wiederholte Stunde (25.10.2026 02:30, beide Male):** **UTC-Form `Z`** statt `TZID`. Alternative: immer `TZID` (gemessen im Integrationslauf: ical.js/Thunderbird liest die Ortszeit dann als den zweiten Durchlauf, die erste Stunde verschiebt sich um eine Stunde).
- **D9 Wer "Als Format speichern" darf:** **`event.submit` der Organisation (Or, Ap) und die Redaktion**. Alternative: nur Redaktion (`format.manage`).
- **D10 Archiv für `member`:** **Kerndaten und `shared`** wie PLAN 5.4. Alternative: nur angemeldete Personen mit Organisation.
- **D11 Nachbereitung** als eigener Reiter `/dossiers/:id/nachbereitung`. Alternative: Abschnitt in der Übersicht.
- **D12 Mitveranstalter** (PLAN §18 Nr. 3) und das Abo-Timing (Nr. 2, B3): **bleiben offen**; der Feed nennt nur die Hauptorganisation.
- **D13 `since` und Entfernte:** Verbraucher bauen bei Bedarf neu auf; Alternative: ein Tombstone-Feld oder ein zweiter Endpunkt `/feed/removed` (Stufe B, wenn der Astro-Loader es braucht).
- **D14 Bibliothek ohne eigene Dokumente** (`library.manage`): **so lassen**; Alternative: `owner = library` mit Editor wie in PLAN 7.3 als Nachfolger-Meilenstein.
- **D15 Fixture-Inhalte:** Filmtitel, Termine, Zahlen sind **erfunden**; Luis kann echte aus dem WordPress-Bestand (Stufe M6, `legacy_wp`) liefern.
- **D16 Google/Apple:** manuell durch Luis oder die Redaktion mit der Schrittfolge aus dem Protokoll; ohne Bestätigung bleibt die Abnahmezeile unvollständig.
- **D17 Roundtrip-Gate (offen aus M4, 29/30 Dateien weichen ab):** Rückblick und Master-Anleitung nutzen den Standardmodus des Gates (Textarea); die Entscheidung über den Tiptap-Serializer bleibt bei Luis.

## 14. Verzeichnisbesitz

Drei Builder, jeder schreibt nur in seinen Bereich. Konflikte löst die Orchestrierung. Kopien aus dem Upstream mit Kopf `Copied from STUPA-Workflow@93c33d6 <pfad>` (Nachbauten "Pattern from") und Eintrag in `PROVENANCE.json` (Modus `U`); nichts wird übernommen, ohne dass der Builder die Quelle gelesen hat. Kein Commit und kein Push vor dem Review; im letzten Schritt entsteht `feat/m5-archiv` mit gescopten Commits (`feat(formats)`, `feat(archive)`, `feat(followup)`, `feat(search)`, `feat(public)`, `feat(worker)`, `feat(frontend)`, `test`, `docs`). Kein Eingriff in Live-Systeme. Werkzeuge wie M4: `nix run nixpkgs#ruff`/`#basedpyright`, `pytest` mit `LD_LIBRARY_PATH` (libstdc++, libmagic), Playwright-Browser über `nix build nixpkgs#playwright-driver.browsers`, Dienste neu starten mit `systemctl --user restart stupa-api stupa-worker stupa-ng`; Details und Fallen stehen in `docs/M4-ABNAHME.md` und `docs/M3-ABNAHME.md`.

| Builder | Besitzt | Aufgaben |
|---|---|---|
| **backend-archiv** | `backend/app/modules/{formats,archive,followup,library,search}/**` (neu), Migration `0006_archive_feed` samt `models.py`-Anteilen (`formats/models.py`, Änderungen in `events/models.py`, `dossier/models_documents.py`), `backend/seeds/formats.yaml`, Seed-Lader, `tests/unit/{formats,archive,followup,library,search}`, `tests/integration/{archive,search}`, `tests/fixtures/{movienight.yaml,search/*}`, `scripts/m5_acceptance.py`, `scripts/pilot_check.py`, `docs/M5-ABNAHME.md` | Abschnitte 2.1 bis 2.5, 2.7, 3, 4, 5, 6, 7 (Endpunkt `view=calendar`, Datei `events/calendar.py`), Ganztägigkeit, Ort, Rahmen (`facts`) |
| **backend-archiv** (kleine Hook-Ausnahmen außerhalb der Module, nur diese Stellen) | `pipeline/{transitions.py, snapshot.py, guards/content.py, reasons.py, service.py}` (T09-Hook, Phase der Checkliste, `FixAction`), `dossier/{guard_data.py, documents*.py, models_documents.py, counts.py}` (Format-Besitz, `retrospective`, `followupOpen`), `events/{schemas.py, writer.py, presenter.py, card_extras.py, cards.py, listing.py, router.py, access.py}` (neue Felder, Ganztägigkeit, `view=calendar`), `files/access.py` und `dossier/attachments_router.py` (Archivpfad), `notifications/{kinds.py, templates/de/*}` (zwei Kinds), `worker/followup.py`, `worker/main.py` (Cron-Eintrag `send_followup_reminders`), `audit/actions.py`, `api_routers.py`, `deploy/db/roles.sql`, `tests/unit/test_route_authz_inventory.py` (Routen), `.claude/skills/{be-events,be-pipeline,be-notifications}/SKILL.md`, neu `.claude/skills/be-archive/SKILL.md`, `CLAUDE.md`, `README.md` | Tabelle 3.1 bis 3.6, Klon-Hooks, Palette-Daten |
| **backend-public** | `backend/app/modules/publicapi/**` (`ics/`, `ics_router.py`, `cache.py`, `cursor.py`, `textsafe.py`, `allowlist.py`, Erweiterungen von `service.py`, `schemas.py`, `router.py`), `backend/worker/public_cache.py`, `app/middleware.py` und `app/shared/errors.py` (öffentliche Präfixe), `app/main.py` (ICS-Router), `app/settings.py` und `.env.example` (drei Einstellungen), `pipeline/actions.py` (Auslöser des Cache-Jobs), `deploy/web/nginx.conf`, `tests/schema/feed-v2.json`, `tests/golden/ics/*`, `tests/unit/publicapi/**`, `tests/integration/publicapi/**`, `tests/_support/canary.py`, `.github/workflows/ci.yml` (Job `restore-smoke`, Schemathesis), `.github/ISSUE_TEMPLATE/pilot-feedback.md`, `.claude/skills/be-public/SKILL.md` (neu), `pyproject.toml` (Abhängigkeiten `markdown-it-py`, `nh3`; dev `icalendar`; `fail_under = 97`) | Abschnitte 2.5 (CHECK-Texte liefert backend-archiv in der Migration), 2.6 (View-SQL wörtlich), 8, 9, 10 |
| **frontend** | `frontend/**` | Abschnitt 11 und 7 (Kalender-Grid): Routen, Nav, I06, I18, I19, I20, Palette, Kalender, Nachbereitung, Ort-Dialog, Rahmen-Feld, Typen, i18n, `PROVENANCE.json`-Einträge der Kopien, `e2e/m5.spec.ts`, `.claude/skills/frontend/SKILL.md` |

Schnittstellen (gemeinsamer Vertrag, Reihenfolge): (1) **backend-public** liefert zuerst `publicapi/allowlist.py`, die Item-Modelle und `feed-v2.json`; **backend-archiv** schreibt danach die Migration `0006` mit allen Tabellen und Spalten aus Abschnitt 2 und der View aus 2.6 und meldet "Migration steht"; (2) **backend-archiv** liefert Formate, Nachbereitung, Klon und Archivpfad (3, 4); **backend-public** Feed, Cache, ICS und Kanarienvogel (8, 9, 10) parallel dazu; (3) Suche und Bibliothek (5, 6) und der Kalender-Endpunkt (7); (4) das Frontend baut gegen den laufenden Dev-Stack und gegen `HttpTestingController`-Antworten; es beginnt mit `shared/ui/calendar-grid`, der Palette und den Typen, weil diese Teile von keinem neuen Endpunkt abhängen. Die Orchestrierung führt vor dem Review `ruff`, `basedpyright`, beide Test-Suiten, `npm run lint|typecheck|test|build`, `alembic upgrade head` auf frischer DB und `python -m scripts.m1_acceptance` bis `m5_acceptance` aus.
