# M1-Kontrakt: Durchstich

Verbindlich für alle fünf Builder (backend-kopie, frontend-shell, infra, backend-events, frontend-events) in Meilenstein M1. Quellen: `PLAN.md` §2, §3, §4, §5, §8, §11, §12, §16.1 und `ENTSCHEIDUNGEN.md` im Plan-Verzeichnis, Upstream `STUPA-Workflow@93c33d6` (U) und `ui-kit@8ad3782`. Pfade `U ...` sind relativ zu `upstream/STUPA-Workflow`.

Wo dieser Kontrakt dem PLAN widerspricht, gewinnt der Kontrakt, und die Abweichung steht in Abschnitt 10. Was in Upstream **nicht** belegt ist, ist als "neu" markiert.

## 1. Ports, Namen, Netz

| Ding | Wert |
|---|---|
| Compose-Projekt | `name: stupa-events` (nie `antragsplattform`) |
| Compose-Datei | `deploy/docker-compose.yml`, Overlay `deploy/docker-compose.keycloak.yml` |
| `web` (nginx + SPA) | `127.0.0.1:8081:80`, feste IP `172.29.10.10` |
| `postgres` | `127.0.0.1:5434:5432`, Postgres 16, DB `events`, Extensions `pgcrypto, citext, btree_gist, pg_trgm, unaccent` |
| `redis`, `minio`, `clamav` | nur intern, kein Host-Port |
| `api`, `worker`, `migrate` | nur intern; Redis-Queue-Name `events` |
| Dev-IdP `keycloak` | `127.0.0.1:8090:8080`, Image `quay.io/keycloak/keycloak:26.0`, `start-dev --import-realm` (Muster `U deploy/docker-compose.keycloak.yml`) |
| Netz `internal` | Bridge, `ipam` Subnetz `172.29.10.0/24`; `FORWARDED_ALLOW_IPS=172.29.10.10` |
| Verbotene Host-Ports | 8080, 5433 (Workflow-Stack), `FORWARDED_ALLOW_IPS=*` |
| Buckets | `events-attachments` (privat), `events-public` (Derivate), `events-backups`; `files/storage.py` legt fehlende Buckets selbst an (`U backend/app/modules/files/storage.py:80`) |

### Dev-IdP Keycloak

Der Upstream liefert die Realm-Datei **nicht** mit (`U deploy/docker-compose.keycloak.yml` mountet `./keycloak`, das Verzeichnis fehlt im Repo und steht in der Root-`.gitignore`). Infra schreibt `deploy/keycloak/stupa-events-realm.json` neu.

| Eigenschaft | Wert |
|---|---|
| Admin-Konsole | `http://127.0.0.1:8090`, `admin` / `admin` |
| Realm | `stupa-events` |
| Client | `stupa-events`, confidential, Standard Flow mit PKCE S256, Secret `stupa-events-dev-secret-0001` (>= 16 Zeichen, `U backend/app/settings.py:101`) |
| Redirect-URI | `http://localhost:8081/api/auth/callback`, Web-Origin `http://localhost:8081` |
| Scopes | `openid email profile offline_access` |
| Claim `groups` | Mapper "Group Membership", `full.path=false`, in ID-Token, Access-Token und Userinfo |
| Gruppen | `events-editor`, `events-fsi-organizer`, `events-fsi-submitter`, `events-makers-organizer` |
| Issuer | `http://host.docker.internal:8090/realms/stupa-events` (ohne Schrägstrich am Ende, so schreibt Keycloak `iss`; `U backend/app/settings.py:89-98`) |

Der Issuer muss für Browser **und** Container gleich auflösen (Upstream-Muster): `extra_hosts: ["host.docker.internal:host-gateway"]` auf `api` und `worker`, einmalig `127.0.0.1 host.docker.internal` in `/etc/hosts` des Hosts. Keycloak läuft mit `KC_HOSTNAME_STRICT=false`, sodass der Issuer aus dem Host-Header abgeleitet wird. Die Browser-URL bleibt trotzdem `http://localhost:8081`.

| Testnutzer | Passwort | Gruppe |
|---|---|---|
| `editor` | `password` | `events-editor` |
| `organizer-fsi` | `password` | `events-fsi-organizer` |
| `submitter-fsi` | `password` | `events-fsi-submitter` |
| `organizer-makers` | `password` | `events-makers-organizer` |

Alle Nutzer haben `email` (`<name>@example.test`, `emailVerified=true`), Vor- und Nachname. Jede Zeichenfolge in Realm und Compose ist ein reines Wegwerf-Fixture und gehört **nie** in einen echten IdP. Der Kopf der Compose-Datei trägt die Warnung wie im Upstream. Der Authentik-Provider `stupa-events` (PLAN 5.6) bleibt Doku in `docs/authentik/**`.

## 2. Umgebungsvariablen

Namen sind exakt die Feldnamen aus `U backend/app/settings.py` (pydantic-settings, `case_sensitive=False`), sofern nicht "neu". `deploy/.env.example` führt jede Variable, `test_env_example_settings_parity` hält beides gleich. Die Dev-Werte stehen in `deploy/.env.dev.example` (infra) und nie echte Secrets im Repo.

| Variable | Dev-Wert | Anmerkung |
|---|---|---|
| `ENVIRONMENT` | `development` | Prod: `production` |
| `STRICT_SECURITY` | `true` | |
| `LOG_LEVEL` | `INFO` | |
| `PUBLIC_BASE_URL` | `http://localhost:8081` | Basis für Feed-`url` und `image.url` |
| `LOCAL_TIMEZONE` | `Europe/Berlin` | |
| `DATABASE_URL` | `postgresql+asyncpg://events_app:<pw>@postgres/events` | Rolle `events_app` (neu: Rollenname) |
| `DB_MIGRATION_URL` | `postgresql+asyncpg://events_migrator:<pw>@postgres/events` | Rolle `events_migrator`; `env.py` fällt bei leerem Wert auf `DATABASE_URL` zurück |
| `PUBLIC_DATABASE_URL` | `postgresql+asyncpg://events_public:<pw>@postgres/events` | **neu**; nur `publicapi` nutzt diese Verbindung |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `ARQ_QUEUE_NAME` | `events` | **neu**, Queue des Workers |
| `SESSION_SECRET` | >= 16 Zeichen | |
| `MAGIC_LINK_SECRET` | entfällt | Magic-Link/Applicant fliegt raus (PLAN 2.4); backend-kopie entfernt Feld, `.env.example`-Zeile und Tests |
| `FORWARDED_ALLOW_IPS` | `172.29.10.10` | nie `*` |
| `CSRF_ENABLED`, `CSRF_COOKIE_NAME`, `CSRF_HEADER_NAME` | `true`, `XSRF-TOKEN`, `X-XSRF-TOKEN` | unverändert |
| `CORS_ALLOW_ORIGINS` | leer | |
| `COOKIE_SECURE` | `false` (Dev), `true` (Prod) | |
| `SESSION_COOKIE_NAME` | `ev_session` | Upstream `ap_session`; **neu benannt**, weil Cookies nicht portgetrennt sind und `localhost:8080` (Workflow) sonst kollidiert |
| `OIDC_TX_COOKIE_NAME` | `ev_oidc_tx` | Upstream `ap_oidc_tx`, aus demselben Grund |
| `SESSION_REVALIDATE_HOURS` | `4` | E24 |
| `SESSION_REVALIDATE_GRACE_HOURS` | `24` | E24 |
| `OIDC_ISSUER` | `http://host.docker.internal:8090/realms/stupa-events` | |
| `OIDC_CLIENT_ID` | `stupa-events` | |
| `OIDC_CLIENT_SECRET` | `stupa-events-dev-secret-0001` | |
| `OIDC_REDIRECT_URL` | `http://localhost:8081/api/auth/callback` | |
| `OIDC_POST_LOGOUT_REDIRECT_URL` | `http://localhost:8081/` | |
| `OIDC_SCOPES` | `openid email profile offline_access` | |
| `OIDC_GROUPS_CLAIM` | `groups` | |
| `BOOTSTRAP_ADMIN_SUBJECTS`, `BOOTSTRAP_ADMIN_EMAILS` | leer | |
| `SMTP_HOST` u. a., `MAIL_FROM`, `MAIL_FROM_NAME`, `MAIL_DEFAULT_LANG` | `SMTP_HOST` leer | Worker loggt und verwirft Mail ohne Host; `MAIL_FROM=noreply@events.local` |
| `MINIO_ENDPOINT` | `minio:9000` | |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Dev-Wegwerfwerte | |
| `MINIO_SECURE` | `false` | |
| `MINIO_BUCKET` | `events-attachments` | Upstream-Default `attachments` |
| `MINIO_PUBLIC_BUCKET` | `events-public` | **neu**, Derivate |
| `ATTACHMENT_MAX_BYTES` | `10485760` | Poster, 10 MiB (PLAN 3.3) |
| `CLAMAV_HOST`, `CLAMAV_PORT` | `clamav`, `3310` | eigener Container (E23) |
| `BACKUP_BUCKET` | `events-backups` | Upstream-Default `backups` |
| `BACKUP_AGE_RECIPIENT`, `BACKUP_AGE_IDENTITY_FILE`, `BACKUP_RETENTION_COUNT` | leer, leer, `14` | |
| `RATE_LIMIT_ENABLED` | `true` | |
| `EDITOR_FOUR_EYES` | `false` | **neu**, E06; wirkt erst, wenn der Guard `four_eyes` in M3 scharf wird (M1: Stub) |
| `WEB_PORT` | `8081` | nur Compose |
| `POSTGRES_PASSWORD`, `EVENTS_APP_PASSWORD`, `EVENTS_MIGRATOR_PASSWORD`, `EVENTS_PUBLIC_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Dev-Wegwerfwerte | nur Compose, **neu** |

Nicht übernommen (Workflow-spezifisch): `TYPST_*`, `PDF_*`, `ALTCHA_*` (B), `OAUTH_*` und `MCP_PACKAGE_DIR` (D), `WEBHOOK_*`, `APPLICANT_*`, `GUEST_*`, `DELEGATION_VOTING_ENABLED`, `DEADLINE_REMINDER_LEAD_MINUTES`, `MAX_APPLICATION_PAYLOAD_BYTES`, `MAX_TICKET_PAYLOAD_BYTES`, `GRAVATAR_*` und die `RL_*`-Limits der Antrags-, Ticket-, Meeting- und Protokoll-Routen. Behalten bleibt `RL_DEFAULT_WRITE_*` und `RL_ATTACHMENTS_PER_HOUR`; backend-kopie entscheidet je Feld und hält die Parität.

## 3. Datenbankrollen und Rechte (`deploy/db/roles.sql`)

Muster: `U deploy/db/roles.sql`, zweistufig, idempotent (DO-Blöcke), keine Passwörter im Repo (`ALTER ROLE ... PASSWORD` danach aus dem Secret-Store, im Dev-Compose per `deploy/db/init-dev.sh`).

| Rolle | Login | Zweck |
|---|---|---|
| `events_migrator` | ja | DDL, Eigentümer aller Tabellen, Funktionen und Views |
| `events_app` | ja | Laufzeit von `api` und `worker` (`DATABASE_URL`) |
| `events_audit_writer` | nein | optionaler Audit-Grant (Migration `0001` setzt ihn bedingt wie `U` Migration 0006) |
| `events_public` | ja | nur `publicapi` (`PUBLIC_DATABASE_URL`) |

**Stufe 1, vor `alembic upgrade head`**: die vier Rollen anlegen; `GRANT CONNECT ON DATABASE events TO events_app, events_migrator, events_public`; `GRANT USAGE ON SCHEMA public TO events_app, events_public`; Default-Privilegien für Objekte von `events_migrator`: an `events_app` **nur** `SELECT, INSERT, UPDATE` auf Tabellen (4.5: `events_app` ohne `DELETE`) und `USAGE, SELECT` auf Sequenzen; `events_public` bekommt per Default **nichts**; `REVOKE ALL ON SCHEMA public FROM PUBLIC`.

**Stufe 2, nach `alembic upgrade head`** (braucht die Tabellen):

- `audit_entry`: `events_app` nur `INSERT, SELECT`; `REVOKE UPDATE, DELETE, TRUNCATE`.
- `event_revision`, `event_status_event`: `events_app` nur `INSERT, SELECT`; `REVOKE UPDATE, DELETE, TRUNCATE`. Der Append-only-Trigger bleibt als zweite Schicht.
- `DELETE` für `events_app` nur dort, wo der kopierte Code es braucht (Sessions/Transaktionstabellen). Die Liste pflegt backend-kopie in `test_db_grants.py`; fachliche Tabellen (`event`, `attachment`, `organization`, `category`) bleiben ohne `DELETE`.
- `events_public`: `REVOKE ALL` auf alle Tabellen und Views, danach `GRANT SELECT ON public_event_v`. Die View gehört `events_migrator` und läuft ohne `security_invoker`; deshalb braucht `events_public` keinen Zugriff auf `event`, `organization`, `category`, `attachment`.

`test_db_grants.py` (Integration) prüft: `events_public` kann `public_event_v` lesen, `SELECT` auf `event` scheitert mit `InsufficientPrivilege`; `events_app` kann `DELETE FROM event` und `UPDATE audit_entry` nicht; `events_app` kann kein DDL.

## 4. API-Vertrag M1

Alle Pfade unter `/api`. JSON camelCase (`_CamelModel`, `extra="forbid"`), Zeiten ISO-8601 mit Offset (UTC auf der Leitung, `Z`), Fehler ausnahmslos `application/problem+json`.

### 4.1 Problem+JSON

Form: `{type, title, status, code, detail?, errors?[{field,msg}], traceId?}` (`U backend/app/shared/errors.py:76-84`). `type` ist `app://error/<code>`. Erweiterung (neu): `AppError` bekommt `extensions: dict[str, Any] | None`, die der Handler in den Body mischt (backend-kopie, PROVENANCE-Modus `U`). Codes:

| Status | `code` | Wann |
|---|---|---|
| 401 | `unauthorized` | keine Session |
| 403 | `forbidden` | Rolle fehlt, Objekt aber sichtbar (z. B. Submitter bearbeitet fremdes Dossier derselben Org) |
| 404 | `not_found` | kein Leserecht (kein Existenz-Orakel, 5.1) oder unbekannte ID |
| 409 | `conflict` | `rev` veraltet oder Zustand schon gewechselt (Optimistic Locking) |
| 409 | `field_locked` | Feld im aktuellen Zustand nicht änderbar (4.1) |
| 409 | `invalid_transition` | Übergang im Ist-Zustand nicht definiert |
| 413 | `payload_too_large` | Poster > 10 MiB |
| 415 | `unsupported_media_type` | MIME-Sniff nicht JPEG/PNG/WebP |
| 422 | `validation_error` | Pydantic/Query-Fehler (`errors[]`) |
| 422 | Code des ersten Blockers (z. B. `image_required`) | Guard verweigert; Zusatzfeld `reasons[]` |
| 429 | `rate_limited` | |
| 503 | `service_unavailable` | Storage aus |

`reasons[]` (Guard-Verweigerung und `GET .../guards/...`): Liste von `{code, field | null, severity: "blocker" | "warning", messageKey, fixAction | null}`. `code` des Problems ist der `code` des **ersten** Blockers in fester Guard-Reihenfolge (`field_missing`, `start_in_past`, `image_required`, `four_eyes`). `fixAction` ∈ `fill_field | change_date | upload_poster | null`. `messageKey` ist ein i18n-Schlüssel (`guards.<code>`), das Frontend übersetzt.

### 4.2 Typen

```
Me            { sub, email|null, displayName|null, roles[], permissions[], groups[],
                organizations[{slug, role}] }
OrgRef        { id, slug, name, short }
CategoryRef   { id, slug, name, kind }                 kind: format|fachschaft|partner
Attachment    { id, eventId, kind: "poster", displayName, mime, sizeBytes, sha256,
                scanStatus: pending|clean|infected|error,
                altText, credit, rightsBasis: own_work|permission|license|partner_agreement|unknown,
                derivatives: { thumb400, card1200, og1200x630 } | null,   # je {id,width,height}
                supersedesId|null, createdAt }
Event         { id, slug|null, state, publicStatus: scheduled|cancelled|postponed,
                title, summary|null, descriptionMd|null,
                startsAt, endsAt, tzid, allDay,
                organization: OrgRef|null, venueText|null, primaryCategory: CategoryRef|null,
                poster: Attachment|null, imageException: {grantedBy, reason, at}|null,
                rev, createdBy, submittedBy|null, approvedBy|null, createdAt, updatedAt,
                allowedTransitions: ("T01"|"T02"|"T04"|"T05")[] }   # nur UX; Server prüft immer
EventCreate   { title, startsAt, endsAt, tzid = "Europe/Berlin", allDay = false,
                organizationId, venueText?, primaryCategoryId?, summary?, descriptionMd? }
EventPatch    { rev, title?, startsAt?, endsAt?, allDay?, venueText?, primaryCategoryId?,
                summary?, descriptionMd? }                  # alle Felder optional, rev Pflicht
TransitionIn  { note? }                                      # note <= 500 Zeichen
Reason        { code, field|null, severity, messageKey, fixAction|null }
Page<T>       { items[], total, limit, offset }              # U backend/app/shared/paging.py
```

Regeln: `title` 1 bis 200 Zeichen, `summary` <= 200 Zeichen Klartext, `startsAt`/`endsAt` müssen tz-aware sein (naive Werte: 422), `endsAt >= startsAt`, `title`/`summary`/`venueText` ohne Steuerzeichen (DB-CHECK, 3.3). `tzid` in M1 nur `Europe/Berlin`. `allDay=true` wird in M1 mit 422 `validation_error` abgelehnt (kommt mit M5). Die Spalten `all_day`, `starts_on`, `ends_on` und deren CHECK `all_day = (starts_on IS NOT NULL)` legt `0002` trotzdem an, damit die View `allDay` liefert.

### 4.3 Endpunkte (intern, Session-Cookie + CSRF)

| Methode Pfad | Rechte | Request | Response |
|---|---|---|---|
| `GET /api/auth/login`, `GET /api/auth/callback`, `POST /api/auth/logout` | offen/Session | wie Upstream (`U backend/app/modules/auth/router.py:80,133,208`) | Redirect bzw. Logout-URL |
| `GET /api/auth/me` | Session | | `Me`; 401 ohne Session |
| `GET /api/events` | Lesen (5.4) | Query `state?`, `organizationId?`, `q?`, `limit` (1..200, 50), `offset` | `Page<Event>`, in SQL nach `org_ids_for` gefiltert, sortiert nach `startsAt` aufsteigend |
| `POST /api/events` | `event.create` in der Ziel-Org | `EventCreate` | 201 `Event` mit `state="idea"`; `createdBy` aus Session; T00 |
| `GET /api/events/{id}` | Lesen | | `Event`; 404 ohne Leserecht |
| `PATCH /api/events/{id}` | `event.edit`, Umfang nach Zustand | `EventPatch` | `Event` mit `rev + 1`; 409 `conflict` bei altem `rev`; 409 `field_locked` ab `in_review` (Ausnahmen unten) |
| `POST /api/events/{id}/transitions/{T01\|T02\|T04\|T05}` | Rolle nach 6 | `TransitionIn` | 200 `Event`; 422 mit `reasons[]`; 409 `invalid_transition`/`conflict`; 403 Rolle |
| `GET /api/events/{id}/guards/{T01\|T02\|T04\|T05}` | Lesen | | 200 `{ transition, allowed: bool, reasons: Reason[] }`; berechnet, nie gespeichert |
| `POST /api/events/{id}/poster` | `dossier.attach` | multipart: `file`, `altText` (1..250), `credit` (1..200), `rightsBasis` | 201 `Attachment` (`scanStatus="pending"`, setzt `hero_attachment_id`; ein früheres Poster wird via `supersedesId` ersetzt, nie gelöscht) |
| `POST /api/events/{id}/image-exception` | `event.image_exception` (nur `editor`) | `{ reason }` (>= 10 Zeichen) | 200 `Event` mit `imageException`; gilt nur für diese Event-ID; auditiert |
| `GET /api/events/{id}/poster/file?variant=thumb400\|card1200` | Lesen | | Bytes des Derivats; nur intern, Session nötig (`Cache-Control: private`) |

PATCH-Umfang (4.1 verkürzt auf M1): `idea` und `planning`: alle Felder für Org-Rollen. `in_review`, `approved`, `live`: 409 `field_locked`. Poster-Upload: in `idea`/`planning` für Org-Rollen und `editor`, in `in_review` nur `approver`/`editor`, ab `approved` 409 `field_locked`. Jede Mutation schreibt in derselben Transaktion `event_revision` (neue `rev`) und `audit_entry`; Zustandswechsel zusätzlich `event_status_event`. Der Router committet.

Poster-Pipeline: Upload prüft MIME per Sniff (`image/jpeg`, `image/png`, `image/webp`), codiert mit Pillow neu (Bombenschutz, EXIF raus), legt das Original in `events-attachments` ab, der Worker (`worker/scan.py`) scannt mit ClamAV, setzt `scan_status`, und `worker/derive.py` (backend-events) erzeugt WebP-Derivate `thumb_400`, `card_1200`, `og_1200x630` in `events-public`. `derivatives` bleibt bis dahin `null`. Ein Poster zählt für `image_required` erst bei `scanStatus="clean"` **und** vorhandenen Derivaten.

Zustandsändernde Routen sind idempotent über `rev` (`UPDATE ... WHERE state = :from AND rev = :rev`, Rowcount 1, sonst 409). `PipelineService.fire` ist der einzige Schreibweg auf `state` (4.5).

### 4.4 Endpunkte (öffentlich)

Router in `publicapi`, ausschließlich `PUBLIC_DATABASE_URL`, `events_public`. Eintrag in `PUBLIC_ALLOWLIST` von `test_route_authz_inventory`. Antworten setzen nie `Set-Cookie`, lösen keine Session auf (Test).

`GET /api/public/feed/events`: Query `from?` (ISO), `to?`, `category?` (Slug), `org?` (Slug), `limit` (1..500, 100). Sortierung `startsAt`, dann `id`. `changedSince` und `cursor` folgen in M5. Header `Cache-Control: public, max-age=300, stale-while-revalidate=60`, `ETag` (Hash der Antwort), `304` bei `If-None-Match`. Kein CORS.

```json
{
  "schema": 2,
  "generatedAt": "2026-10-18T12:00:00Z",
  "items": [{
    "id": "uuid",
    "slug": "2026-11-05-movienight-film-a",
    "title": "...",
    "summary": "...",
    "startsAt": "2026-11-05T18:00:00Z",
    "endsAt": "2026-11-05T21:00:00Z",
    "allDay": false,
    "tzid": "Europe/Berlin",
    "status": "scheduled",
    "organization": { "id": "uuid", "name": "Fachschaft Informatik", "short": "FSI" },
    "venueText": "Kinosaal 9-133",
    "categories": [{ "slug": "kino", "name": "Kino", "kind": "format" }],
    "image": { "url": "http://localhost:8081/api/public/media/3fa9c1d2e4b5a678-card_1200.webp",
               "width": 1200, "height": 675, "alt": "...", "credit": "..." },
    "url": "http://localhost:8081/e/2026-11-05-movienight-film-a"
  }]
}
```

Regeln: `image` ist in M1 immer gefüllt, außer bei einem Event mit gültiger Ausnahme (dann `null`). `categories` enthält in M1 die Hauptkategorie. `venueText` ist `null`, wenn der Ort nicht öffentlich ist; in M1 gilt: `location_precision = hidden` ist Standard, also liefert die View `venueText` erst, wenn T04 `location_precision` gesetzt hat. Da M1 keinen Ort-Bestätigungsdialog hat, ist `venueText` in M1 **immer öffentlich** und die Spalte `location_precision` kommt erst mit M3 (Abweichung 10.4). Nie im Feed: Entwürfe, `event_status_event.note`, `image_exception`, Ersteller, interne IDs außer `id`, `organization`-Kontaktdaten, Hex-Farben. Antwortformen sind ausschließlich `PublicEventOut` (kein ORM-`model_dump` in `publicapi`, Lint-Test).

`GET /api/public/media/{derivativeId}.webp`: `derivativeId = <sha256[:16]>-<variant>`, `variant ∈ thumb_400 | card_1200 | og_1200x630`. Die Route prüft über `public_event_v` (Spalte `hero_derivatives`), dass das Derivat zu einem öffentlichen Event gehört (sonst 404), und streamt aus `events-public`. `Cache-Control: public, max-age=31536000, immutable`, `Content-Type: image/webp`, kein `Set-Cookie`. Ersetzen eines Posters ergibt ein neues `sha256` und damit eine neue ID.

### 4.5 `public_event_v` (Migration `0002`)

Zeilen nur mit `state IN ('live','followup','archived')` und (gültiges Poster, also `scan_status = 'clean'` und Derivate vorhanden, **oder** gültige `image_exception`). Allowlist-Spalten: `id, slug, title, summary, starts_at, ends_at, all_day, tzid, public_status, organization_id, organization_name, organization_short, venue_text, category_slug, category_name, category_kind, hero_sha, hero_derivatives, hero_alt, hero_credit, updated_at`. Joins auf `organization`, `category`, `attachment` stecken in der View.

## 5. Gruppen, Rollen, Scope

Gruppenschema (PLAN 5.2, 5.6): `events-<org>-<rolle>` mit `<org>` = `organization.slug` und `<rolle>` ∈ `viewer | submitter | organizer | approver`; global `events-editor` (Rolle `editor`), `events-admin` (`admin`, M2), `events-stupa` (`stupa`, M2). Die Gruppenauswertung ist eine reine Funktion `parse_group(name) -> GroupGrant | None` mit dem Muster `^events-(?P<org>[a-z0-9][a-z0-9-]*)-(?P<role>viewer|submitter|organizer|approver)$` in `app/shared/permissions.py` (Besitzer backend-kopie). Alles, was nicht passt oder mit `events-system:` beginnt, wird verworfen (5.1). Die Tabelle `group_mapping(oidc_group UNIQUE, role, organization_id NULL)` legt `0002` an; in M1 wird sie nicht befüllt und nur zuerst abgefragt, das Schema greift danach (Admin-UI folgt M2).

| OIDC-Gruppe | Rolle | Geltung | M1-Testnutzer |
|---|---|---|---|
| `events-editor` | `editor` | global | `editor` |
| `events-fsi-organizer` | `organizer` | Org `fsi` | `organizer-fsi` |
| `events-fsi-submitter` | `submitter` | Org `fsi` | `submitter-fsi` |
| `events-makers-organizer` | `organizer` | Org `makers` | `organizer-makers` |
| `events-<org>-approver` | `approver` | Org `<org>`, nur wenn `organization.trusted` | (kein Nutzer in M1) |
| `events-<org>-viewer` | `viewer` | Org `<org>` | (kein Nutzer in M1) |

**Scope-Regel:** Organisation kommt immer aus dem Gruppennamen (`<org>`), nie aus Body oder Query. `editor` ist global. `Principal.has(perm, org_id=...)` entscheidet, nie `principal.roles` (5.1). `org_ids_for(session, principal, perm) -> None | set[UUID]` liefert `None` für global, sonst die Org-Menge; jede Liste filtert in SQL. `POST /events` mit `organizationId` außerhalb der Org-Menge: 404 (kein Orakel). Der Slug-zu-ID-Abgleich passiert in `orgs/scope.py` (backend-events, eine Abfrage je Request); `Principal` selbst trägt nur Slugs. `GET /api/auth/me` liefert `organizations[{slug, role}]` allein aus `parse_group` ohne DB.

**Berechtigungen M1** (Katalog in `app/shared/permissions.py`, Namen aus 5.3):

| Recht | submitter | organizer | approver | editor |
|---|---|---|---|---|
| `event.read_all` | | | | ja |
| (Lesen eigene Org) | ja | ja | ja | ja |
| `event.create` (in eigener Org) | ja | ja | ja | ja |
| `event.edit` (Umfang 4.1) | nur **eigene** Dossiers in `idea`/`planning` | alle der Org | alle der Org | alle |
| `event.submit` (T02) | | ja | ja | ja |
| `event.approve` (T04, T05) | | | ja (eigene trusted Org) | ja |
| `event.image_exception` | | | | ja |
| `dossier.attach` (Poster) | eigene, `idea`/`planning` | Org, `idea`/`planning` | Org, bis `in_review` | alle, bis `in_review` |

`viewer` liest nur. Unter T01 gilt zusätzlich: Submitter nur eigene (`created_by = Session`). Admin-Bypass (M2) umgeht nie die harten Guards `image_required` und `four_eyes`.

## 6. Zustandstabelle M1

Enum `event_state` (DB-CHECK und `StrEnum`, alle acht Werte schon in `0002`): `idea`, `planning`, `in_review`, `approved`, `live`, `followup`, `archived`, `withdrawn`. Übergänge nach `followup`, `archived`, `withdrawn` und zurück (T03, T06 bis T12) kommen in M3; in M1 sind sie nicht erreichbar und die Route kennt sie nicht (Pfadparameter `Literal["T01","T02","T04","T05"]`, sonst 422 `validation_error`).

| Id | Von nach | Wer | Guards (M1) | Nach dem Commit (idempotent, Schlüssel `event:<id>:rev:<n>:<action>`) |
|---|---|---|---|---|
| T00 | (neu) nach `idea` | Submitter, Organizer, Approver, Editor | Org im Scope | `event_revision` 1, Audit |
| T01 | `idea` nach `planning` | Submitter (eigene), Organizer, Editor | `hasField(title, startsAt, organizationId)` | |
| T02 | `planning` nach `in_review` | Organizer, Approver, Editor | `hasField(title, summary, startsAt, endsAt, primaryCategoryId, venueText)`, `dateInFuture` | `submitted_by` setzen |
| T04 | `in_review` nach `approved` | Approver (eigene trusted Org), Editor | `image_required`, `dateInFuture` (laufend erlaubt: `endsAt > now`), `fourEyes` als Stub (gibt immer "erfüllt" zurück, der Guard ist verdrahtet und deshalb in `reasons` auflistbar) | Slug vergeben (`<YYYY-MM-DD>-<slug-aus-title>`, bei Kollision `-2`), `public_seq`, `approved_by` setzen, Derivate sicherstellen |
| T05 | `approved` nach `live` | Approver, Editor, (Worker ab M5) | T04-Guards erneut: `image_required`, `dateInFuture` | Feed sichtbar (View) |

Guards sind reine Funktionen `(snapshot, actor, now) -> list[Reason]` in `pipeline/guards.py`. M1-Codes: `field_missing` (blocker, `field` gesetzt, `fixAction=fill_field`), `start_in_past` (blocker, `change_date`), `image_required` (blocker, `upload_poster`; erfüllt mit Poster `clean` + Derivate + `altText` + `credit` + `rightsBasis ≠ unknown`, oder `image_exception`), `four_eyes` (M1 nie ausgelöst). Fehlt das Poster am `in_review`-Event, antwortet T04 mit 422 `image_required`; derselbe Zustand per **direktem SQL** (`UPDATE event SET state='approved' ...`) scheitert am Trigger `enforce_publish_image` (E41) mit SQLSTATE `23514`. Der Trigger greift bei `INSERT OR UPDATE OF state, hero_attachment_id, image_exception` für `approved` und `live`. Ein zweiter Trigger auf `attachment` verhindert, dass das Poster eines `approved`/`live`-Events seinen `scan_status` verschlechtert oder ausgeblendet wird (`retired_at`).

Weitere DB-Netze in `0002`: CHECK `ends_at >= starts_at`; `state IN ('idea','withdrawn') OR organization_id IS NOT NULL`; Append-only-Trigger auf `event_revision` und `event_status_event` (M1 noch ohne `privacy_redact`-Ausnahme, die kommt mit M3); Unique `(event_id, rev)`.

## 7. Verzeichnisbesitz

Jeder Builder schreibt nur in seinen Bereich. Konflikte löst die Orchestrierung, nicht der Builder. Kopf-Docstring "Copied from STUPA-Workflow@93c33d6 <pfad>" und PROVENANCE-Eintrag (Modus `K` oder `U`) für jede kopierte Datei; `PROVENANCE.json` führt jeder Builder für **seine** kopierten Dateien als Zeilen im gemeinsamen Format `{"upstream":{"repo":"STUPA-MAKERS/STUPA-Workflow","commit":"93c33d6"},"files":[{"path","source","mode"}]}` (Zusammenführung durch infra am Ende, bis dahin je Builder Teil-Datei `PROVENANCE.<builder>.json` im Repo-Root).

| Builder | Besitzt | Zusatz |
|---|---|---|
| backend-kopie | `backend/**` außer `backend/app/modules/{orgs,taxonomy,events,pipeline,publicapi,dossier}/**` | liefert App-Fabrik, Settings, DB, Middleware, Problem+JSON (inkl. `extensions`), Auth (OIDC, Sessions, `/auth/me`, Bootstrap), Audit, Files, Media, Mail, Worker-Gerüst, `shared/permissions.py` (Rollenkatalog, `parse_group`, `Principal.has`, `org_ids_for`-Signatur), `migrations/versions/0001_baseline.py` (Extensions, `de_unaccent`, `immutable_unaccent`, `audit_entry` samt Trigger), `tests/_support`, Test-Konfiguration |
| frontend-shell | `frontend/**` außer `frontend/src/app/features/**` | Shell (Rahmen `rail/public/bare/pending`), Auth, i18n (de), Theme, PWA-Update, Kit-Submodul `@ 8ad3782`, `shared/ui`, Routing mit Lazy-Routen auf `features/**` |
| infra | `deploy/**`, `.github/**`, `flake.nix`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, `docs/authentik/**` | Compose, Overlay Keycloak samt Realm-JSON, `.env.example`, `db/roles.sql`, nginx, `backup.sh`, CI, `test_compose_lint`-Fixtures, `PROVENANCE.json`-Merge |
| backend-events | `backend/app/modules/{orgs,taxonomy,events,pipeline,publicapi,dossier}/**`, `backend/migrations/versions/0002_*`, `backend/tests/{unit,integration}/{events,pipeline,publicapi}/**` | `0002_events_core` (Tabellen `organization`, `group_mapping`, `category`, `event`, `event_revision`, `event_status_event`, `attachment`, Trigger, Views, Seeds aus `backend/seeds/*.yaml`), Pipeline, Poster-Endpunkt, `worker/derive.py` (Modul `dossier`), Feed |
| frontend-events | `frontend/src/app/features/**`, `frontend/e2e/**` | Seiten I02-light (Aufgaben), I05 (Neues Event), I07-light (Dossier-Kopf, Poster, Guard-Liste, Übergangsknöpfe), Login-Rückkehr, Playwright-E2E |

Schnittstellen zwischen den Besitzern:

- `0001` hat genau diese Revisions-ID `0001_baseline`, `0002` die ID `0002_events_core` (<= 32 Zeichen), ein Head. PLAN 3.1 nennt "die erste Revision" mit Triggern und Views; in M1 kann sie keine Tabellen enthalten, die erst `0002` anlegt, daher die Trennung (Abweichung 10.3).
- Das Worker-Gerüst (`worker/main.py`) liest Funktionen aus einer Registrierungsliste; `backend-events` hängt `derive_poster` über `app/modules/dossier/worker_jobs.py` mit der Konstante `WORKER_FUNCTIONS` an, backend-kopie importiert sie bedingt (`try/except ImportError` ist verboten: backend-kopie legt eine leere `WORKER_FUNCTIONS = ()`-Datei am Pfad an, backend-events überschreibt sie).
- `app.main.create_app` bindet Router über `app/api_routers.py` (backend-kopie, Liste); backend-events ergänzt seine Router dort durch Absprache in einem einzigen Commit am Schluss (Orchestrierung).
- `tests/integration/conftest.py` (backend-kopie) hat eine zentrale Truncate-Liste `TRUNCATE_TABLES`; backend-events ergänzt seine Tabellen in `backend/tests/integration/events/conftest.py` per Fixture, nicht in der geteilten Datei.
- Frontend-Features dürfen nur über `core/`- und `shared/ui`-Barrel-freie Pfadimporte auf die Shell zugreifen; das API-Client-Modell (`features/**/api`) bekommt seine Typen aus Abschnitt 4.2 per Hand, nicht aus generiertem Code.

## 8. Testbefehle

| Ziel | Befehl (Arbeitsverzeichnis) |
|---|---|
| Backend Lint | `uv run ruff check . && uv run ruff format --check .` (`backend/`) |
| Backend Typen | `uv run basedpyright` (`backend/`) |
| Backend Unit | `uv run pytest -m 'not integration and not e2e and not live'` (`backend/`) |
| Backend Integration (Docker nötig, testcontainers) | `uv run pytest -m integration` (`backend/`) |
| Migrationen | `uv run alembic heads` (genau ein Head) und `uv run alembic upgrade head` auf frischer DB (`backend/`) |
| Frontend Lint | `npm run lint` (`frontend/`) |
| Frontend Typen | `npm run typecheck` (`frontend/`) |
| Frontend Unit | `npm test` (`frontend/`, Jest) |
| Frontend Build | `npm run build` (`frontend/`, Produktions-Build) |
| Compose | `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.keycloak.yml --env-file deploy/.env.dev config -q` |
| Stack hoch | `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.keycloak.yml --env-file deploy/.env.dev up -d --build` |
| Compose-Smoke | `deploy/smoke.sh` (infra): `GET http://127.0.0.1:8081/api/health` 200, CSP-Header in jeder nginx-Location |
| E2E | `npx playwright test` (`frontend/`, Browser über `nix build nixpkgs#playwright-driver.browsers`, gegen den laufenden Stack) |
| Secrets | `gitleaks detect` (Repo-Wurzel) |

Pflicht-Tests M1 (Namen fest, damit das Review sie findet): `test_provenance`, `test_audit_hash` (Hash der Kette identisch zu Upstream-Golden), `test_env_example_settings_parity`, `test_db_grants`, `test_route_authz_inventory`, `test_rbac_matrix` (Rolle × {eigene Org, fremde Org} × Endpunkt), `test_transitions_matrix`, `test_guards`, `test_publish_property` (hypothesis: keine API-Folge erreicht `live` ohne Poster/Ausnahme), `test_direct_sql_publish_rejected` (Trigger), `test_public_feed_schema` (gegen `backend/tests/schema/feed-v2.json`), `test_public_no_set_cookie`, `test_camel_case_contract`, `test_no_eval`. Coverage-Gate M1: `pipeline` und `publicapi` 100 % Branch, gesamt >= 90 % (Anhebung auf 97 % bis M5; Abweichung 10.5).

## 9. Abnahmekriterium M1 (wörtlich aus PLAN §16.1)

> Login über Authentik zeigt `/auth/me` mit Rolle aus einer Gruppe; ein Testkonto `events-fsi-organizer` legt ein Dossier an, lädt ein Poster mit Alt-Text und Credit hoch, fragt Freigabe an; ein Testkonto `events-editor` gibt frei; das Event erscheint im Feed; ohne Poster antwortet die Freigabe mit 422 `image_required`, auch per direktem SQL-Update scheitert es (Trigger); `alembic upgrade head` auf frischer DB grün; Audit-Kette verifiziert; `test_provenance` und Audit-Hash-Test grün; `compose-smoke` findet CSP in jeder Location; VM-RAM gemessen und ClamAV-Entscheidung (E23) dokumentiert; `backup.sh` und ein Restore einmal gelaufen; `CLAUDE.md` und Skills für `auth`, `events`, `pipeline` angelegt

Lokale Lesart in dieser Phase (Dev-IdP statt Authentik, kein VM): "Authentik" gilt als Keycloak mit denselben Gruppen (PLAN: "bis W2 ein Dev-IdP mit denselben Gruppen"); "freigibt" heißt T04 und T05 durch `events-editor`; die Punkte VM-RAM und Restore auf dem Server entfallen lokal und stehen in `README.md` als offen.

## 10. Abweichungen vom PLAN (zur Nachführung durch Luis)

1. **Feed-Hülle**: PLAN 8.2 beschreibt `{schema, generatedAt, data}` mit `start/end/timezone/organizers/orgShort`; der Kontrakt nutzt `items[]` mit `startsAt/endsAt/tzid/organization/venueText/categories/url` (Auftrag). `tests/schema/feed-v2.json` folgt dem Kontrakt, PLAN 8.2 zieht nach.
2. **Mediapfad**: PLAN 8.1 `/api/public/media/<id>/<variant>.webp`, Kontrakt `/api/public/media/{derivativeId}.webp` mit `derivativeId = <sha256[:16]>-<variant>`.
3. **Erste Migration**: Roh-DDL aus PLAN 3.1 verteilt sich auf `0001_baseline` (Extensions, Textsuche, Audit) und `0002_events_core` (alles, was Event-Tabellen braucht: `enforce_publish_image`, Append-only, Views).
4. **Ort**: `location_precision`, `geo_override`, `lat/lon` und der Guard `location_unconfirmed` fehlen in M1; `venue_text` ist öffentlich. Vor dem Pilot (M5) nachziehen.
5. **Coverage**: Gate in M1 90 % gesamt statt 97 %; die 100 %-Branch-Pflicht für `auth, audit, files, media` greift mit `coverage_critical.py` erst, wenn die Module nicht mehr nur kopiert sind (M2).
6. **Env-Name**: `PUBLIC_DATABASE_URL` statt PLAN 8.1 `DB_PUBLIC_URL`; Cookies `ev_session`, `ev_oidc_tx` statt `ap_*`.
7. **Gruppenauswertung**: PLAN 5.6 "Namen stehen nur in `group_mapping`, nie im Code" gilt ab M2; in M1 wertet `parse_group` das Schema aus (Auftrag), `group_mapping` ist angelegt und wird zuerst befragt.
8. **Guards T04/T05**: `attachmentsScanned`, `rightsComplete` (persons_depicted, consent_note) und `titleClean` aus PLAN 4.3 fehlen in M1 (Scan-Status steckt in `attachment_poster_ok`, Rechte-Felder kommen mit M2/M3). `dateInFuture` bindet nur T04 (erste Freigabe), nicht T05: ein freigegebenes Event darf nach seinem Ende nicht an der Veröffentlichung hängen. `fourEyes` ist ein Stub.
9. **Revisionen enthalten Freitext**: `event_revision.payload` hält `description_md`, `venue_text` und `created_by` als Klartext in einer Append-only-Tabelle; sie ist vom Löschkonzept (PLAN 3.5, 8.9) nicht erfasst. Wie das Löschkonzept damit umgeht, ist vor Stufe B zu entscheiden. Das Audit hält nur IDs.
10. **Medienroute und Cache-Header**: `/api/public/media/{derivativeId}.webp` statt `<derivativeId>/<variant>.webp` (siehe 2); der Feed trägt nur `ETag` und `Cache-Control`, kein `Last-Modified` (304 über `If-None-Match`).
11. **Scan-Ende**: Nach `scan_max_tries` setzt der Worker `scan_status='error'` und schreibt einen Audit-Eintrag; das Poster bleibt unveröffentlichbar.
12. **MinIO-Konto**: Die App nutzt in M1 die MinIO-Root-Zugangsdaten (`MINIO_ACCESS_KEY`/`SECRET_KEY` = Root). Ein auf die zwei Buckets beschränktes Service-Konto ist offen (siehe `M1-ABNAHME.md`).
