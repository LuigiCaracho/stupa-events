# B3-Kontrakt: Get started, Abos, Listmonk

Stand 2026-10-24, gelesen auf `feat/b1-public` (HEAD `543433d`, Migration-Head `0008_public_site`). Der Branch `feat/b3-abos` entsteht beim ersten Builder aus `feat/b1-public`; alle Builder committen ihre Teile sofort, nichts wird gepusht. Verbindlich: `stupa-events-plan/ENTSCHEIDUNGEN.md` (inkl. Kurskorrektur 21.10.), `PLAN.md` §3.3 (Abo-Tabellen), §8.3, §8.7, §8.9, §11.3, §11.7, §15.2 (P06 bis P09), §16.2 (B2-Token-Teil, B3, Gate B3), §18 Minor 2, dazu `lesen/extern.md` §1 (Listmonk) und `docs/B1-KONTRAKT.md` (Public-Routen setzen nie Cookies, Abschnitt 2.9; Profil-ICS und Token wurden dort nach B3 verschoben, 8.1). "Nur Belegtes": Was ich im Arbeitsbaum oder im Plan gelesen habe, steht mit Datei; was ich nicht gelesen oder nicht gegen eine laufende Listmonk-Instanz geprüft habe, steht als "Annahme" oder "Builder prüft".

Regeln wie bisher: Upstream-Konventionen, camelCase mit `extra=forbid`, Problem+JSON, tz-aware, Public-Routen ohne Cookie, Angular standalone mit signals und ui-kit, i18n de, Jest, Playwright, `PROVENANCE.json` für kopierten Upstream-Code, kleine Dateien mit Kopf-Docstring, keine Trennkommentare. Code und Commits Englisch, UI Deutsch gegendert. Kein Eingriff in Live-Systeme (nur lokales Docker und die Dev-Units `stupa-api`, `stupa-worker`, `stupa-ng`). NixOS-Fallen wie in `docs/M*-ABNAHME.md` und `deploy/dev-up.sh` (LD_LIBRARY_PATH für libstdc++ und libmagic). Commits tragen den Trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_013NodAsFyipzEwD8Nird4cT`.

## 0. Umfang

**Drin:** Get started P06 (Fragebogen, Profil, Ergebnis), Abos P07 (Mail-Teil, Verweis auf Get started), Bestätigen P08, Verwalten P09, Profil-ICS mit Token und Rotation (B2-Rest), eigene Double-Opt-in, Nachweis, ALTCHA und Limits, `ListmonkPort` mit Outbox, Abgleich, Digest als Listmonk-Entwurf mit Freigabe, Löschkonzept-Jobs, Admin-Auskunft und -Löschung, Dev-Stack mit Listmonk und Mailpit.

**Nicht drin:** Listmonk-Betrieb in Produktion, Absenderdomain, Auftragsverarbeitung (Weiche W3, Gate B3), Datenschutztexte (B5, hier nur die Vorlage `docs/B3-DATENSCHUTZ.md`, 5.9), EN-Parität und PWA-Cache der Abo-Seiten (B4), Push, Karten, Kategorie-Zusätze per Mail-Link an fremde Adressen (bewusst nicht gebaut, 3.2).

## 1. Lückenanalyse (Ist am Arbeitsbaum, Soll aus PLAN)

| # | Soll | Ist (Beleg) | Lücke und Maßnahme |
|---|---|---|---|
| L1 | Abo-Tabellen (PLAN 3.3) | keine; `grep interest` findet in `backend/app`, `migrations`, `seeds` nichts; Head ist `0008_public_site` | Migration `0009_subscriptions` (Abschnitt 2) |
| L2 | Rolle `events_subs` | `deploy/db/roles.sql` kennt `events_migrator`, `events_app`, `events_public`, `events_audit_writer`; `deploy/db/init-roles.sh` setzt nur drei Passwörter | Rolle, Grants, Passwort, `SUBS_DATABASE_URL` (2.5, 7) |
| L3 | Dritte DB-Verbindung | `publicapi/db.py` hat die Engine der Rolle `events_public` (`pool_size=4, max_overflow=2`), keine Subs-Engine | `subscriptions/db.py` nach demselben Muster (eigene URL, kein Fallback), Pool 3 plus 1 (2.5) |
| L4 | ALTCHA | `backend/app/shared/` hat kein `altcha.py`; `shared/antiabuse.py` (Kopf: "ALTCHA comes with the public forms in stage B") kennt nur Body-Limit und Rate-Limit; `settings.py` hat keine `altcha_*`-Felder; Upstream hat `shared/altcha.py`, `modules/antiabuse/router.py` (`GET /altcha/challenge`), `altcha_enabled` (HMAC-Secret gesetzt) | Kopie mit `PROVENANCE`-Eintrag (5.1) |
| L5 | Rate-Limit je Ziel-Adresse | `shared/ratelimit.py` hat `RedisRateLimiter` (fail-open, Sliding Window) und `InMemoryRateLimiter`; `publicapi/ratelimit.py` zählt nur je IP | Limit je IP über denselben Limiter, Limit je Adresse zusätzlich als DB-Zähler (5.2), weil Redis fail-open ist |
| L6 | Listmonk-Client | keiner; `shared/ssrf.py` hat `assert_allowed_url(url, allowlist=...)` mit IP-Prüfung auf nicht-globale Adressen (Loopback und private Netze sind gesperrt) | `listmonk_client.py`; die Ziel-URL ist Betreiber-Konfiguration, nie Nutzereingabe, darum Host-Allowlist plus Scheme-Prüfung, IP-Sperre abschaltbar für genau diese Hosts (4.1) |
| L7 | Mailversand für Abo-Mails | `notifications/queue.py` (`ArqMailQueue`, `_job_id` = Idempotenzschlüssel), `notifications/mail.py` (`MailMessage`, `compute_idempotency_key`, Logs nur Domains), `worker/mail.py` (`send_mail`, `build_sender`: SMTP oder `CapturingMailSender`, der nur im Speicher des Worker-Prozesses sammelt), Templates unter `notifications/templates/de`, Sandbox in `notifications/templating.py` | DOI-, Verwaltungs- und Hinweis-Mail über dieselbe Pipeline; für E2E ein Mailpit im Dev-Stack statt In-Memory-Capture (7) |
| L8 | Profil-ICS | `publicapi/ics_router.py` kennt `/ics/all.ics`, `/ics/k/{slug}.ics`, `/ics/e/{slug}.ics`; Writer deterministisch (`ics/writer.py`), Kategorie-Snapshots im Redis (`publicapi/cache.py`, `serving.ics_document`); nginx hat `ev_ics_redacted` und `Referrer-Policy: no-referrer` für `/ics/`; `proxy_cache` schließt `/ics/p/` aus (B1 5.1) | Route `/ics/p/{token}.ics` im Modul `subscriptions`, Zusammensetzung aus den Kategorie-Snapshots (3.5) |
| L9 | Rechte `digest.release`, `privacy.erase`, `subscriber.stats` | in PLAN 5.3 genannt; `grep` in `backend/app` findet keine; Katalog in `shared/permissions.py` (`ROLE_PERMISSIONS`) | ergänzen: `admin` alle drei, `editor` zusätzlich `digest.release` und `subscriber.stats` |
| L10 | Worker-Jobs `listmonk_outbox`, `reconcile_listmonk`, `build_digest_drafts`, `purge_expired` | `worker/main.py` führt Cron-Jobs für Advance, Purge, GC, Reminder, Public-Cache, Scans; PLAN 6.5 nennt die B-Jobs mit "1 min, täglich, wöchentlich, täglich" | vier Module `worker/{outbox,reconcile,digest,privacy}.py`, Registrierung in `WorkerSettings` (4.7); Queue `events` (`max_jobs 2`) |
| L11 | Frontend | `features/public/public.routes.ts` kennt `abos` (`pages/subscribe`, zeigt "kommt bald" für Mail und Profil), aber weder `start`, `bestaetigen/:token` noch `abo/:token`; ui-kit hat `app-stepper`, `app-segmented`, `app-checkbox`, `app-input`, `app-dialog`, `app-button`, `app-toast`, `app-switch`; `app-qr-code` und `app-filter-select` fehlen im Kit (`vendor/ui-kit`), `shared/ui` hat `filter-select`, `note`, `empty-state`, `skeleton` | Abschnitt 6; kein QR (Auftrag), Chips aus `shared/ui/filter-select` |
| L12 | nginx | `nginx.conf` leitet `/api`, `/ics`, `/e/`, `/k/`, `/suche` an die API, der Rest ist SPA; `ev_ics_redacted` nur für `/ics/p/`; kein Rate-Limit-Block für POSTs | `/abo/` und `/bestaetigen/` redigiert loggen, `no-referrer`, kein `proxy_cache`; `limit_req` für `/api/public/subscriptions` (7.4) |
| L13 | Löschpfad für Personendaten | PLAN 3.1: nur über `privacy_*`-Funktionen (`SECURITY DEFINER`); im Baum gibt es noch keine (`grep privacy_` in `app` und `migrations` leer); Upstream hat `modules/privacy` (anderer Zweck) | Funktionen in Migration `0009` (2.4); `events_subs` bekommt kein `DELETE` auf Tabellen |
| L14 | Mail-Adressen in Logs | Konvention: Logs ohne Adressen, Tokens, Suchtexte (PLAN 11.6, `mail.py` loggt Domains) | Kanarienvogel-Test deckt Abo-Pfad ab (8.2) |
| L15 | E2E-Zugriff auf Mails | `frontend/e2e/` hat `m1` bis `m5b`, `public.spec.ts`; keinen Mail-Zugriff | Mailpit-API im Dev-Stack, Helfer `e2e/support/mailpit.ts` (6.7, 7) |

## 2. Datenmodell: Migration `0009_subscriptions`

`revision = "0009_subscriptions"`, `down_revision = "0008_public_site"` (ID unter 32 Zeichen, genau ein Head). Muster wie `0006` bis `0008`: Roh-DDL und `op.create_table`, additiv, `downgrade()` löscht Funktionen und Tabellen in umgekehrter Reihenfolge. Konventionen aus PLAN 3.1: `uuid` PK mit `gen_random_uuid()`, `timestamptz`, Enums als CHECK plus `StrEnum`, snake_case in der DB. Die Extension `pgcrypto` ist seit Baseline aktiv (PLAN 2.1; Builder prüft `0001_baseline.py`).

### 2.1 Tabellen

**`interest`** (Seed, Fragebogen-Antworten zu Kategorien): `slug text PK` (Muster `^[a-z][a-z0-9-]{1,39}$`), `label text NOT NULL`, `category_ids uuid[] NOT NULL`, `sort int NOT NULL`, `active bool NOT NULL DEFAULT true`. Seeds in `backend/seeds/interests.yaml` (PLAN 2.3 nennt `seeds/interests.yaml`), geladen über `subscriptions/interest_seed.py` mit `reference_id("category", slug)` aus `taxonomy/reference.py`. Vorschlag für Version 1 (Slugs der Kategorien belegt in `taxonomy/reference.py`; die Zuordnung ist ein Vorschlag, Luis bestätigt, Weiche B3-1):

| `interest.slug` | Label (Chip) | Kategorien |
|---|---|---|
| `party` | Partys und Feiern | `party`, `campusfest`, `festival`, `get-together` |
| `kultur` | Kino, Konzerte, Kultur | `kino`, `konzert` |
| `sport` | Sport und Ausfahrten | `ausfahrt`, `skiausfahrt`, `skydiving`, `kart-fahren` |
| `gaming` | Gaming und LAN | `lan-party` |
| `lernen` | Workshops und Lernen | `workshop`, `repair-cafe`, `cooking-class` |
| `sitzung` | Sitzungen und Gremien | `sitzung` |

`fachschaft:<slug>` ist **kein** Tabellenwert: er wird beim Auflösen aus den aktiven Kategorien mit `kind = 'fachschaft'` gebildet (`fachschaft-fsi`, `fachschaft-tec`, `fachschaft-tex`, `fachschaft-ls`, `fachschaft-nxt`, `esb-stuco`; Builder prüft die genauen Slugs in `taxonomy/reference.py`). `fachschaft:<slug>` mit `<slug>` = Slug der Fachschaft-Kategorie ohne das Präfix `fachschaft-` (Sonderfall `esb-stuco`: Slug unverändert). Partner-Kategorien (`makers`, `oikos`, `care`, `ekhg`, `hochschule`) haben kein Interesse; Lücke, bleibt über `/abos` (ICS je Kategorie) erreichbar.

**`subscriber`**:

| Spalte | Typ | Regel |
|---|---|---|
| `id` | uuid PK | |
| `email_enc` | bytea NULL | `pgp_sym_encrypt(email, PGCRYPTO_EMAIL_KEY)` (E18); `NULL` nur bei `status = 'erased'` |
| `email_hmac` | text NULL UNIQUE | HMAC-SHA-256 (Hex) der kanonischen Adresse mit `EMAIL_HASH_KEY` (5.3); `NULL` nur bei `erased`; die Spalte heißt `email_hmac` (Auftrag), PLAN und E18 sagen `email_hash` (Abweichung 9.2) |
| `status` | text NOT NULL | CHECK `pending|confirmed|unsubscribed|bounced|erased` |
| `confirm_token_hash` | text NULL | SHA-256-Hex des DOI-Tokens, gesetzt solange `pending`, sonst `NULL` |
| `confirm_expires_at` | timestamptz NULL | Erzeugung plus 24 h |
| `manage_token_hash` | text NULL | SHA-256-Hex des Verwaltungs-Tokens (Magic-Link) |
| `manage_expires_at` | timestamptz NULL | Erzeugung plus 2 h |
| `consent_text_version` | text NOT NULL | z. B. `2026-10-1`, Text im Code (`consent.py`), nie nachträglich geändert (Golden-Test) |
| `consent_categories` | text[] NOT NULL | Kategorie-Slugs, die der Einwilligungstext nannte |
| `consent_at` | timestamptz NOT NULL | Zeitpunkt der Anmeldung (Einwilligung gegeben) |
| `confirmed_at` | timestamptz NULL | Zeitpunkt des POST-Knopfs (DOI-Nachweis) |
| `unsubscribed_at` | timestamptz NULL | |
| `listmonk_subscriber_id` | int NULL | |
| `mails_day` | date NOT NULL DEFAULT current_date, `mails_count` int NOT NULL DEFAULT 0 | harter Zähler "höchstens 3 Abo-Mails je Adresse und Tag" (5.2) |
| `created_at`, `updated_at` | timestamptz NOT NULL | |

Keine IP und kein User-Agent im Datensatz (PLAN 3.3 "Keine IP im Datensatz"); das vom Auftrag erwogene `consent_ip_hash` entfällt (Abweichung 9.3). CHECK: `status = 'erased' OR (email_enc IS NOT NULL AND email_hmac IS NOT NULL)`. Index `ix_subscriber_status_created (status, created_at)` für die Löschjobs.

**`subscription_profile`**: `id uuid PK`, `subscriber_id uuid NULL REFERENCES subscriber(id) ON DELETE SET NULL` (UNIQUE, wenn nicht NULL: höchstens ein Profil je Person), `questionnaire_version int NOT NULL`, `interests jsonb NOT NULL` (Liste der Interessen-Slugs inkl. `fachschaft:<slug>`; "Sitzungen? ja" ist das Interesse `sitzung`), `categories text[] NOT NULL` (aufgelöste Kategorie-Slugs, Eltern- und Kind-Kategorien, höchstens 40), `ics_token_hash text NOT NULL UNIQUE`, `ics_token_rotated_at timestamptz NOT NULL`, `mail_enabled bool NOT NULL DEFAULT false`, `last_fetched_on date NULL`, `created_at`, `updated_at`. `interests` ist JSONB, weil es ein versioniertes Antwortformat ist (PLAN 3.1: JSONB nur für versionierte Formate); gefiltert wird über `categories`, nie über `interests`. `digest_weekday` aus dem Auftrag entfällt: der Digest ist ein Listmonk-Entwurf je Kategorie-Liste, nicht je Person, ein Wochentag je Profil ließe sich nicht erfüllen (Abweichung 9.4). `mail_enabled` ist die Antwort auf "Wie oft Mail?" (wöchentlich = true, nie = false).

**`outbox`** (Listmonk-Aufträge; PLAN nennt sie `listmonk_outbox`, Auftrag `outbox`: Name `outbox`, Abweichung 9.2): `id uuid PK`, `op text NOT NULL` CHECK `upsert|unsubscribe|delete|ensure_list`, `subscriber_id uuid NULL REFERENCES subscriber(id) ON DELETE SET NULL`, `idempotency_key text NOT NULL UNIQUE`, `payload jsonb NOT NULL DEFAULT '{}'` (nie Klartext-Adresse; `delete` trägt `listmonkSubscriberId` und `emailEnc` als Chiffrat, das beim Abschluss auf `NULL` gesetzt wird; `ensure_list` trägt `key`), `state text NOT NULL` CHECK `pending|running|done|dead` (`running` mit `locked_at` für verwaiste Läufe), `attempts int NOT NULL DEFAULT 0`, `next_at timestamptz NOT NULL`, `locked_at timestamptz NULL`, `last_error text NULL` (nur Fehlerklasse und HTTP-Status, kein Antworttext), `created_at`, `done_at`. Index `ix_outbox_due (next_at) WHERE state = 'pending'`. **Idempotenzschlüssel:** `"{op}:{subscriber_id}:{profile_version}"`, wobei `profile_version` die Zahl `subscription_profile.updated_at` in Mikrosekunden ist; eine zweite identische Einreihung kollabiert (`ON CONFLICT DO NOTHING`). Das Worker-Verfahren ist "Sollzustand abgleichen" (4.3), nicht "Delta abspielen": ein verspäteter Auftrag richtet nichts an.

**`listmonk_list`** (nicht im Auftrag, nötig für die Listen-IDs; PLAN legt `category.listmonk_list_id` in die Kategorie, hier in eine eigene Tabelle, damit `events_app` und `events_subs` getrennte Schreibrechte behalten, Abweichung 9.5): `key text PK` (Kategorie-Slug oder `_all`), `listmonk_id int NOT NULL`, `name text NOT NULL`, `archived_at timestamptz NULL`.

**`digest_run`**: `id uuid PK`, `week_start date NOT NULL` (Montag, Berliner Kalender), `list_key text NOT NULL`, `campaign_id int NULL`, `status text NOT NULL` CHECK `draft|released|skipped`, `event_count int NOT NULL`, `released_by_sub text NULL` (OIDC-`sub` des Freigebenden), `released_at timestamptz NULL`, `created_at`, UNIQUE `(week_start, list_key)`.

### 2.2 Views und Rechte auf Views

`events_subs` liest die Views `public_event_v` und `public_category_v` (Digest, Profil-ICS-Fallback) und die Tabelle `interest`. Weitere Tabellen des Systems sieht die Rolle nicht.

### 2.3 Verschlüsselung

`pgp_sym_encrypt` und `pgp_sym_decrypt` laufen in SQL mit dem Schlüssel als Bind-Parameter; der Schlüssel liegt nur in `PGCRYPTO_EMAIL_KEY` (Settings, `min_length=32`). Damit der Schlüssel nicht über Postgres-Fehlerlogs ("DETAIL: parameters") ausläuft, setzt `roles.sql` für die Rolle `log_parameter_max_length = 0` und `log_parameter_max_length_on_error = 0` (beides nur durch Superuser setzbar, `roles.sql` läuft als Superuser; Builder belegt es im Test, 8.2). Entschlüsselt wird nur für Versand (Worker), Auskunft (Admin) und Abgleich.

### 2.4 `privacy_*`-Funktionen (`SECURITY DEFINER`, Eigentümer `events_migrator`, `SET search_path = public, pg_temp`)

`EXECUTE` nur für `events_subs`, `REVOKE ... FROM PUBLIC`. Jede Funktion gibt nur Zähler zurück, nie Zeilen.

| Funktion | Wirkung |
|---|---|
| `privacy_erase_subscriber(p_id uuid)` | löscht das verknüpfte Profil samt Token, setzt `subscriber` auf `status = 'erased'`, überschreibt `email_enc`, `email_hmac`, `confirm_*`, `manage_*`, `consent_categories` (zu `{}`), `listmonk_subscriber_id`; reiht einen `delete`-Auftrag mit Chiffrat ein, **bevor** `email_enc` überschrieben wird (der Auftrag hält die einzige Kopie, bis Listmonk gelöscht ist) |
| `privacy_purge_pending(p_cutoff timestamptz)` | löscht `pending`-Subscriber mit `created_at < p_cutoff` (Standard: jetzt minus 48 h); ein verknüpftes Profil bleibt als reines Kalender-Profil (`subscriber_id` wird `NULL`, `mail_enabled = false`) |
| `privacy_anonymize_unsubscribed(p_cutoff timestamptz)` | wie Erase für `unsubscribed` und `bounced` mit `unsubscribed_at < p_cutoff` (Standard: minus 30 Tage) |
| `privacy_purge_profiles(p_cutoff date)` | löscht Profile mit `coalesce(last_fetched_on, created_at::date) < p_cutoff` und `subscriber_id IS NULL` (Standard: minus 12 Monate; Profile mit Mail-Abo laufen nicht ab) |
| `privacy_purge_outbox(p_cutoff timestamptz)` | löscht `done`-Aufträge älter als 30 Tage, `payload.emailEnc` ist dann längst `NULL` |

Die Python-Seite ruft die Funktionen über die Subs-Verbindung auf und schreibt danach den Audit-Eintrag über die App-Verbindung (`audit.service.record`), ohne PII: Aktion, Zähler, Auslöser (`system` oder `sub`). Die Audit-Hash-Kette läuft unter `events_app` und `events_audit_writer`; die Subs-Rolle schreibt nie ins Audit.

### 2.5 Rolle `events_subs` (`deploy/db/roles.sql`, zwei Stufen wie die anderen)

Stufe 1: `CREATE ROLE events_subs LOGIN` (im `DO`-Block), `CONNECTION LIMIT 6`, `statement_timeout = '3s'`, `idle_in_transaction_session_timeout = '5s'`, die beiden Log-Parameter-GUCs aus 2.3, `GRANT CONNECT`, `GRANT USAGE ON SCHEMA public`. Stufe 2 (nach `alembic upgrade head`): `SELECT, INSERT, UPDATE` auf `subscriber`, `subscription_profile`, `outbox`, `listmonk_list`, `digest_run`; `SELECT` auf `interest`, `public_event_v`, `public_category_v`; **kein** `DELETE`, **kein** `TRUNCATE`; `EXECUTE` auf die fünf `privacy_*`-Funktionen. Die Default-Privileges für `events_app` gelten nur für `events_app`; die Subs-Tabellen bekommt `events_app` **nicht** (`REVOKE ALL ... FROM events_app` für die fünf Tabellen und `interest`-Schreibrechte: `events_app` darf `interest` lesen und ändern, falls ein Admin-Formular folgt; heute nur `SELECT`). Der bestehende Abschnitt "events_public reads the public views only" bleibt, `events_public` bekommt keine Subs-Tabelle. `init-roles.sh` setzt `EVENTS_SUBS_PASSWORD`; `docker-compose.dev.yml` und `docker-compose.yml` reichen es durch; `test_db_grants_roles_sql.py` erhält `events_subs` in `ROLES`.

`subscriptions/db.py`: `get_subs_engine()` mit `SUBS_DATABASE_URL` (kein Fallback, Fehler `ServiceUnavailableError`), `pool_size=3, max_overflow=1` (Limit 6 für API und Worker zusammen; B1-Abnahme dokumentiert, dass eine Rolle mit zu kleinem Limit im gemischten Betrieb überläuft), `get_subs_session()`.

## 3. Flows

Alle Routen unter `/api/public/subscriptions` und `/api/public/getstarted` liegen im Modul `subscriptions`, antworten ohne `Set-Cookie` (der CSRF-Middleware genügt, dass keine Auth-Cookies mitkommen, `middleware.py`: "A request without an auth cookie stays exempt"), mit `X-Robots-Tag: noindex` (`PUBLIC_PREFIXES`) und `Cache-Control: no-store`. Fehler als Problem+JSON mit `code`. Modelle `CamelModel`, `extra=forbid`, Body höchstens 4 KiB (`antiabuse`-Body-Cap).

### 3.1 Fragebogen: `GET /api/public/getstarted/questions`

Antwort `QuestionnaireOut {version: int, questions: [...], consent: {version, template, privacyUrl}}`. Version 1, **fünf Fragen** (innerhalb 4 bis 6):

| # | Id | Frage | Typ | Antwort |
|---|---|---|---|---|
| 1 | `interests` | "Was interessiert dich?" | Mehrfachwahl, Chips aus `interest` (nichts vorausgewählt) | Interessen-Slugs, mindestens 1 |
| 2 | `meetings` | "Interessieren dich Sitzungen und Gremien?" | ja/nein | `true` fügt `sitzung` hinzu |
| 3 | `faculty` | "Zu welcher Fachschaft gehörst du?" | optional, Einfachwahl aus den aktiven Fachschaft-Kategorien | `fachschaft:<slug>` oder leer |
| 4 | `channel` | "Wie möchtest du auf dem Laufenden bleiben?" | Kalender / Kalender und Mail | steuert Schritt 5 |
| 5 | `mail` | Adresse, Einwilligung | nur bei Mail | siehe 3.2 |

PLAN 15.2 P06 beschreibt fünf Schritte mit "Ausschlüssen" ("Keine Ausfahrten"); der Auftrag verwendet positive Interessen und einen Kanalschritt, Ausschlüsse entfallen, weil `categories[]` im Auftrag positiv ist (Abweichung 9.6). Die Antwort ist ohne Cookie öffentlich cachebar (`Cache-Control: public, max-age=300`, ETag), enthält nichts Personenbezogenes.

`consent.template`: "Ich möchte wöchentlich eine Mail zu {categories}. Abmelden geht jederzeit mit einem Klick." mit `{categories}` = Labels der gewählten Interessen. Die **Version** (`consent_text_version`) benennt Wortlaut und Platzhalter-Regel; Wortlaut-Änderung = neue Version, alte Texte bleiben im Code (`consent.py`, Dict `version -> template`) und im Golden-Test.

### 3.2 Anmelden: `POST /api/public/subscriptions`

Body `SubscribeIn {questionnaireVersion: int, answers: {interests: str[], meetings: bool, faculty: str|null, mail: bool}, email: str|null, consent: {version: str, accepted: bool}|null, altcha: str}`. Validierung: `email` und `consent` Pflicht, wenn `answers.mail`; sonst beide `null`. `consent.version` ungleich der aktuellen: 409 `consent_outdated`.

Antwort **immer 202** `SubscribeOut {profile: {icsUrl, webcalUrl, categories: [{slug, name}]}, mail: {requested: bool}}`, bei Mail ohne Angabe, ob die Adresse bekannt war. Ablauf (ein Pfad, siehe 5.3):

1. ALTCHA prüfen (400 `altcha_invalid` bei ungültig, abgelaufen oder wiederverwendet), Limit je IP (429, 5.2).
2. Antworten auflösen: `resolve_categories(interests, meetings, faculty)` (rein, 8.1); unbekannter Slug: 422 `unknown_interest`; leere Menge: 422 `no_interest`.
3. Profil anlegen: Token `secrets.token_urlsafe(32)`, in der DB nur `sha256(token)`; `icsUrl = {public_base_url}/ics/p/{token}.ics`, `webcalUrl` mit Schema `webcal`. Der Token steht **nur** in dieser Antwort und im Browser (kein Log, keine Mail).
4. Ohne Mail: fertig (Profil ohne `subscriber_id`).
5. Mit Mail: `email_hmac` bilden (5.3), in einer Transaktion `SELECT ... FOR UPDATE` auf die Zeile.
   - **Unbekannt, `unsubscribed`, `bounced` oder `pending`:** Zeile anlegen bzw. auf `pending` setzen, neues `confirm_token`, 24 h gültig, Profil verknüpfen, DOI-Mail einreihen (Mail-Queue, `idempotency_key = compute_idempotency_key("doi", subscriber_id, token_hash)`). Wer sich nach Abmeldung erneut anmeldet, durchläuft die DOI neu; `unsubscribed` bleibt bis zum POST-Knopf bestehen (Monotonie).
   - **`confirmed`:** nichts an Interessen oder Listen ändern; Mail "Du bist schon angemeldet" mit Verwaltungs-Link (Magic-Link, 3.4); das neue Profil bleibt ein reines Kalender-Profil. Damit kann niemand fremde Adressen auf zusätzliche Listen setzen (PLAN A09 ohne Pending-Kategorie-Zustand; Abweichung 9.7).
   - **`erased`:** nicht auffindbar (`email_hmac IS NULL`), wie unbekannt.
6. Der Aufruf beantwortet erst nach der Mindestdauer (5.3).

Mail-Zähler (`mails_count` 3 je Adresse und Tag, 5.2): Ist er erreicht, entfällt das Einreihen der Mail, die Antwort bleibt dieselbe.

### 3.3 Bestätigen: Seite P08 und `POST /api/public/subscriptions/confirm`

`GET /bestaetigen/{token}` ist die SPA-Seite P08 (PLAN 15.2 nennt `/bestaetigen/<token>`, der Auftrag `/abo/bestaetigen/{token}`: wir folgen dem PLAN, Abweichung 9.1; sonst wäre `/abo/<manage-token>` mehrdeutig). **Ein GET ändert nie etwas**: der Server liefert nur das Shell-HTML. Die Seite ruft beim Laden `POST /api/public/subscriptions/confirm/preview` `{token}` auf (prüft den Token, ändert nichts, Antwort `{categories: [label]}` oder die 404 von unten), damit sie den Satz mit den Kategorien zeigen kann. Link-Scanner der Hochschulmail führen nur das GET aus und lösen weder Preview noch Bestätigung aus.

`POST /api/public/subscriptions/confirm` Body `{token: str}` (ohne ALTCHA: der Token ist der Beweis; Limit je IP 30/h gegen Raten):
- Treffer auf `confirm_token_hash` mit `status = 'pending'` und `confirm_expires_at > now()`: `status = 'confirmed'`, `confirmed_at = now()`, `confirm_*` auf `NULL`, `profile.mail_enabled = true`, ein `upsert`-Auftrag in der Outbox (Idempotenzschlüssel 2.1), Antwort 200 `{status: "confirmed"}`. Alles in einer Transaktion; Listmonk wird **nicht** synchron aufgerufen (Listmonk down verliert nichts).
- Alles andere (unbekannt, abgelaufen, schon benutzt, Zeile gelöscht): **dieselbe** 404 `invalid_token`, Problem+JSON, gleicher Körper, gleiche Mindestdauer.

### 3.4 Verwalten: Magic-Link und Seite P09

`POST /api/public/subscriptions/manage-link` Body `{email, altcha}`: **immer 202** mit leerem Körper `{}`. Bei `confirmed`: neuer `manage_token` (nur Hash, 2 h), Mail mit `{public_base_url}/abo/{token}`; sonst keine Mail. Gleiche Mindestdauer, gleiches Zählwerk wie 3.2.

`GET /abo/{token}` ist die SPA-Seite P09 (nur Shell, kein API-Aufruf beim GET). Sie lädt `GET /api/public/subscriptions/me` mit dem Token im Header `X-Subscription-Token` (der Auftrag nennt `?token=`; Query-Strings stehen in Proxy-Logs und Browser-Verlauf, ein Header nicht, Abweichung 9.8). Routen:

| Methode, Pfad | Wirkung |
|---|---|
| `GET /api/public/subscriptions/me` | `MeOut {interests, categories: [{slug,name}], mailEnabled, icsUrl: null, hasProfile}`; die ICS-URL ist aus dem Hash nicht rekonstruierbar, darum nie hier |
| `PUT /api/public/subscriptions/me` | `{interests?: str[], mailEnabled?: bool}`: setzt Interessen neu (gleiche Auflösung wie 3.2, Vorrang des Tokens über die Mailbox: der Magic-Link beweist den Besitz der Adresse, neue Kategorien gelten sofort, `consent_text_version` und `consent_categories` werden neu geschrieben, Abweichung 9.7), `mailEnabled` schaltet Mail an oder aus; reiht `upsert` ein |
| `POST /api/public/subscriptions/me/ics-token` | rotiert den ICS-Token, Antwort `{icsUrl, webcalUrl}` einmalig; der alte Hash wird überschrieben (damit ist der alte Token genauso "unbekannt" wie ein nie vergebener) |
| `DELETE /api/public/subscriptions/me` | "Alles abbestellen und Daten löschen": `privacy_erase_subscriber`, Antwort 204; danach liefert jede Route 404 `invalid_token` |

Die Token-Prüfung ist überall dieselbe Funktion (`manage_token_hash = sha256(header)` und `manage_expires_at > now()`), ohne Unterschied zwischen "falsch" und "abgelaufen". Der Token verlängert sich nicht von selbst; die Seite zeigt bei 404 "Dieser Verwaltungslink ist ungültig." und ein Feld "Neuen Link anfordern" (ruft `manage-link`). Ein reines Kalender-Profil (ohne Mail) hat keine Verwaltungsseite; es lebt bis 12 Monate nach dem letzten Abruf (2.4) und wird neu angelegt (Weiche B3-2: Alternative wäre eine Verwaltung per ICS-Token; nicht gebaut, weil der ICS-Token dann zugleich Abruf- und Schreibrecht wäre).

### 3.5 Profil-ICS: `GET /ics/p/{token}.ics`

Teil von B2 (PLAN 16.2). Route in `subscriptions/ics_profile_router.py`, Subs-Verbindung. Verhalten:

- Token-Muster `^[A-Za-z0-9_-]{43}$` (sonst 404, kein 422). Suche über `ics_token_hash = sha256(token)`. **Unbekannt, rotiert, widerrufen und gelöscht geben dieselbe 404** (`calendar not found`, derselbe Körper, `Cache-Control: no-store`, gleiche Antwortzeit: kein früher Rücksprung vor dem DB-Zugriff, Mindestdauer 5.3 gilt nicht, weil der Token 256 Bit hat).
- Inhalt: Vereinigung der Kategorie-Kalender des Profils (`categories`). Zusammengesetzt aus den Kategorie-Snapshots des Workers (`serving.ics_document(pool, session, cache.ics_name(slug), slug, settings)`, PLAN 11.7 "wird aus den gecachten Kategorie-Fragmenten zusammengesetzt, nie aus der DB gerechnet"). `ics_merge.merge(bodies, name)` (rein): Kopf und `VTIMEZONE` einmal, `VEVENT`-Blöcke dedupliziert nach `UID` (ein Event in Eltern- und Kind-Kategorie), sortiert nach `DTSTART` und `UID`, `X-WR-CALNAME:STUPA Events: Mein Profil`, ansonsten Bytes des Writers (CRLF, Faltung). Builder prüft, dass der Writer `VTIMEZONE` nur bei Bedarf schreibt (`ics/writer.py` Kopf: "`TZID` with a `VTIMEZONE` block").
- Header: `Content-Type: text/calendar; charset=utf-8`, `Content-Disposition: inline; filename="stupa-events.ics"`, `Cache-Control: private, max-age=900`, `ETag` aus dem zusammengesetzten Körper, 304 bei `If-None-Match`, `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex`.
- Nebenwirkung: `last_fetched_on = current_date` höchstens einmal je Tag (`UPDATE ... WHERE last_fetched_on IS DISTINCT FROM current_date`), keine Schreibflut.
- Abruf-Limit je IP wie `public_limit`; zusätzlich zählt jede 404 gegen `ics-p-miss:ip` (30/h, Rate-Limit-Schlüssel enthält die IP, nie den Token).
- Nie im Log: nginx loggt `/ics/p/...` redigiert (`ev_ics_redacted`, vorhanden), Uvicorn-Access-Log aus (`--no-access-log` oder Filter, Builder prüft den Start in `deploy/dev-up.sh` und im `Dockerfile`), die App loggt nie Pfad oder Token der Route; Test 8.2.

### 3.6 Abmeldung

Zwei Wege, ein Ergebnis, **monoton**: `unsubscribed` verlässt der Datensatz nur über eine neue DOI (3.2).

1. **Listmonk-Link** (`{{ UnsubscribeURL }}` in jeder Mail): Listmonk setzt Abo-Status je Liste auf `unsubscribed` oder den Subscriber auf `blocklisted`. Listmonk hat nach `extern.md` §1.1 keine ausgehenden Webhooks; die Übernahme erfolgt im Abgleich (4.5) und zusätzlich vor jedem `upsert` (4.3).
2. **Eigene Route:** der Magic-Link-Seite P09 "Mail abstellen" (`PUT me {mailEnabled: false}`) entfernt den Subscriber aus allen Listen (Auftrag `upsert` mit Sollzustand "keine Liste"); "Alles abbestellen und Daten löschen" ist `DELETE me`. Eine Mail-Antwort auf ein "unsubscribe"-Verfahren per `List-Unsubscribe`-Header ist die von Listmonk (`extern.md` §1.1: zum Header steht in der Doku nichts, **Annahme**; Builder prüft in den Mailpit-Mails der Listmonk-Kampagne, ob `List-Unsubscribe` gesetzt ist; falls nicht, Eintrag in `docs/B3-ABNAHME.md` als offenen Punkt).

Abmeldung am Ende: `status = 'unsubscribed'`, `unsubscribed_at`, ein `unsubscribe`-Auftrag (Blocklist in Listmonk, damit nichts versehentlich wieder zustellt). Nach 30 Tagen anonymisiert `privacy_anonymize_unsubscribed` (2.4) und löscht den Listmonk-Datensatz; danach ist die Adresse für uns unbekannt (eine Neuanmeldung wäre eine neue DOI).

## 4. Listmonk-Port

### 4.1 Schnittstelle und Client

`subscriptions/listmonk_port.py` (Protocol, rein, importiert keine HTTP-Bibliothek):

```python
class ListmonkPort(Protocol):
    async def ensure_list(self, key: str, name: str) -> int: ...
    async def find_subscriber(self, email: str) -> ListmonkSubscriber | None: ...
    async def upsert_subscriber(self, email: str, list_ids: set[int], attribs: dict[str, object]) -> ListmonkSubscriber: ...
    async def blocklist(self, subscriber_id: int) -> None: ...
    async def delete_subscriber(self, subscriber_id: int) -> None: ...
    async def list_states(self, list_ids: set[int]) -> AsyncIterator[ListmonkSubscriber]: ...
    async def create_campaign(self, draft: CampaignDraft) -> int: ...
    async def campaign_status(self, campaign_id: int) -> str: ...
    async def start_campaign(self, campaign_id: int) -> None: ...
    async def subscriber_count(self, list_id: int) -> int: ...
```

`ListmonkSubscriber {id, email, status (enabled|blocklisted), lists: dict[int, str] (Status je Liste)}`. `FakeListmonk` (`tests/_support/fake_listmonk.py`) setzt den Port im Speicher um und kann Fehler und Wartezeiten einspielen; er ist die Pflicht-Prüfung der Port-Verträge (`tests/contract/test_listmonk_port.py` läuft gegen Fake **und** gegen den echten lokalen Listmonk, Marker `listmonk`, opt-in wie PLAN 12.4 `contract-listmonk`).

`listmonk_client.py` (httpx, async), Aufrufe auf die dokumentierte API (`extern.md` §1.1):

| Port-Methode | Aufruf |
|---|---|
| `ensure_list` | `GET /api/lists?query=<name>&per_page=all`, sonst `POST /api/lists` (`type: private`, `optin: single`, `tags: ["events"]`); die ID kommt in `listmonk_list` |
| `find_subscriber` | `GET /api/subscribers?query=subscribers.email='<e>'` mit verdoppelten `'`; E-Mail-Adressen mit Steuerzeichen oder Backslash sind schon bei der Annahme abgewiesen (5.3) |
| `upsert_subscriber` | existiert nicht: `POST /api/subscribers` (`name` fest "STUPA Events Abo", `status: enabled`, `lists`, `attribs`, `preconfirm_subscriptions: true`); existiert: `PUT /api/subscribers/lists` (`action: add|remove`, `status: confirmed`) für die Differenz, `PATCH /api/subscribers/{id}` nur für `attribs` (Merge), **nie** `PUT /api/subscribers/{id}` und **nie** `lists` in `PATCH` (Fallen aus `extern.md` §1.3) |
| `blocklist` | `PUT /api/subscribers/{id}/blocklist` (**Annahme**: Endpunkt existiert in v5; Builder prüft gegen die laufende Instanz, sonst `PATCH` mit `status: blocklisted`) |
| `delete_subscriber` | `DELETE /api/subscribers/{id}` |
| `list_states` | `GET /api/subscribers?list_id=<id>&per_page=500&page=n` je Liste |
| `create_campaign` | `POST /api/campaigns` (`name`, `subject`, `lists`, `type: regular`, `content_type: html`, `body`, kein `send_at`): Listmonk legt im Status `draft` an (**Annahme** aus der Statuslogik der Doku, Builder prüft) |
| `start_campaign` | `PUT /api/campaigns/{id}/status` `{status: "running"}` |
| `subscriber_count` | `GET /api/lists/{id}` (Feld `subscriber_count`, **Annahme**) |

Attribute am Subscriber (Auftrag; PLAN 8.7.5 sagt nur `source`, `profile_version`): `{source: "get-started", profile_version, profil_id, kategorien: [slug]}`; nie Token, nie Klartext-Interessen mit Personenbezug über den Slug hinaus (Abweichung 9.9).

Sicherheit des Clients: Basis-URL aus `LISTMONK_URL`, **Scheme `https`** (in `environment=development` auch `http` für Loopback); Host exakt in `LISTMONK_ALLOWED_HOSTS` (`ssrf.assert_allowed_url(url, allowlist=hosts)` für Scheme und Host; die IP-Sperre gegen nicht-globale Adressen entfällt für genau diese Allowlist, weil Listmonk im Docker-Netz oder auf Loopback liegt; Builder ergänzt dafür in `shared/ssrf.py` den Parameter `allow_private: bool = False` und dokumentiert die Änderung in `PROVENANCE.json`). `follow_redirects=False`. Pfadteile nur aus ganzen Zahlen. Timeouts: Verbindung 3 s, Lesen 10 s, gesamt 15 s. Auth: Header `Authorization: token {LISTMONK_API_USER}:{LISTMONK_API_TOKEN}`. Antworttexte kommen nie ins Log (nur Status und Fehlerklasse). Die Namen `LISTMONK_API_USER/TOKEN` folgen PLAN 11.3 (der Auftrag sagt `LISTMONK_USER/TOKEN`, Abweichung 9.10). 429 und 5xx sind wiederholbar, andere 4xx sind `dead`-Kandidaten nach drei Versuchen.

### 4.2 Listen-Schema

Eine private Liste je aktive Kategorie mit `key = category.slug` und Name `events-<slug>` (Präfix `events-`, PLAN A09: API-Rolle nur `events-*`), dazu `_all` mit Name `events-alle`. Alle Listen `optin: single` (die Einwilligung liegt bei uns; `preconfirm_subscriptions: true` erst nach unserer Bestätigung, E16). Listen anlegen: `ensure_list`-Auftrag beim ersten Bedarf eines Upserts, plus Start-Seed im Dev-Stack (7.2). Eine Kategorie auf `active = false` archiviert ihre Liste (`PUT /api/lists/{id}` mit `status: archived`, **Annahme**) und setzt `listmonk_list.archived_at`; nie löschen.

### 4.3 Outbox-Worker (`worker/outbox.py`)

arq-Cron jede Minute, `unique=True`, Queue `events`. Ein Lauf holt bis zu 50 fällige Aufträge (`state = 'pending' AND next_at <= now()`) mit `FOR UPDATE SKIP LOCKED`, setzt `running`/`locked_at`, verarbeitet sie je Subscriber seriell in `created_at`-Reihenfolge. Verwaiste `running`-Zeilen (`locked_at` älter als 5 min) gehen zurück auf `pending`.

**Sollzustand:** `upsert` liest den aktuellen Subscriber und sein Profil, bildet `desired = {} wenn mail_enabled = false, sonst {_all} ∪ {Listen der Profil-Kategorien}` und gleicht mit Listmonk ab. Vorher liest er den Listmonk-Zustand: Ist der Subscriber dort `blocklisted` oder in einer Liste `unsubscribed`, **gewinnt Listmonk**: die Liste wird nicht wieder hinzugefügt; `blocklisted` setzt unseren Datensatz auf `unsubscribed` (Monotonie, 4.5). `unsubscribe` setzt Blocklist und entfernt aus allen Listen; `delete` löscht anhand `listmonkSubscriberId` oder, falls leer, anhand des Chiffrats per `find_subscriber`, und leert danach `payload.emailEnc`.

**Retry:** bei Fehler `attempts += 1`, `next_at = now() + min(30 s * 2^attempts, 1 h)`, nach zehn Versuchen `dead` und Alarm. **Circuit-Breaker:** nach fünf aufeinanderfolgenden Fehlern im selben Lauf bricht der Lauf ab und setzt in Redis einen Schlüssel `listmonk:open` für 5 Minuten, in der Zeit machen weitere Läufe nichts. **Listmonk down:** `confirm` und `delete` laufen bei uns durch, die Outbox wächst, nichts geht verloren; das Alarm-Kriterium "Rückstand älter als 1 h" erscheint als Kennzahl `outboxLagSeconds` und `outboxDead` auf der Statusseite I25 (`GET /api/admin/status`, bestehende Route erweitert; Builder prüft den Ort).

### 4.4 Digest (`worker/digest.py`, `subscriptions/digest*.py`)

Wöchentlich (arq-Cron Montag 05:00 UTC, UTC vs. Berlin ist PLAN §18 Minor 5 und bleibt dort offen) erzeugt `build_digest_drafts` für jede Liste `key` (Kategorie-Listen und `_all`) mit mindestens einem kommenden Event (Berliner Woche Montag bis Sonntag der nächsten sieben Tage, Quelle `public_event_v` über `events_subs`; Kategorie-Listen enthalten Events der Kategorie und ihrer Kinder) **und** mindestens einem Subscriber (`subscriber_count`) einen Kampagnen-**Entwurf** (E17: nie sofort senden). Je Liste ein `digest_run` (UNIQUE `(week_start, list_key)`, Wiederholung ist ein No-op; vor dem Anlegen sucht der Job eine Kampagne mit Namen `events-digest-{week_start}-{key}` in Listmonk, damit ein Absturz zwischen Listmonk-Aufruf und DB-Schreiben keine zweite Kampagne erzeugt). Kampagne: Betreff "STUPA Events: Das ist diese Woche los", Inhalt aus einem Jinja-Template (`SandboxedEnvironment`, `StrictUndefined`, Autoescape, Muster `notifications/templating.py`) mit Karten je Event (Titel, Zeit in Berliner Wandzeit, Ort, Link `{public_base_url}/e/{slug}`), Fuß mit `{{ UnsubscribeURL }}` und Link zu `/abos`.

**Go-Template-Injektion:** Listmonk wertet den Inhalt als Go-Template. Ein Event-Titel `{{ .Subscriber.Email }}` würde ausgewertet. Darum ersetzt der Builder in allen eingesetzten Event-Feldern `{{` durch `&#123;&#123;` und `}}` durch `&#125;&#125;`; nur die Fußzeile trägt echte Platzhalter. Test 8.1.

**Freigabe:** Das Recht `digest.release` (Rolle `editor`, `admin`) gibt es als Knopf "Digest freigeben" in I25 (`POST /api/admin/digests/{id}/release` → `start_campaign`) oder im Listmonk selbst. Der Knopf ist gesperrt, solange `subscriber_count(list) != Zahl unserer `confirmed`-Subscriber mit `mail_enabled` und dieser Liste` (PLAN 8.7.7, A09) oder `listmonk:open` gesetzt ist. Der Abgleich markiert `digest_run.status = 'released'` auch dann, wenn die Freigabe im Listmonk geschah (`campaign_status != draft`). "Automatisch planen nach drei fehlerfreien Läufen" (E17) ist nicht gebaut (Abweichung 9.11).

### 4.5 Abgleich (`worker/reconcile.py`, täglich 03:10 UTC)

1. Alle Listen aus `listmonk_list` seitenweise lesen (`list_states`).
2. **Eigene gewinnt, außer bei Abmeldung:** (a) Listmonk `blocklisted` oder in **allen** unseren Listen `unsubscribed`: unser Subscriber wird `unsubscribed` (nur wenn er `confirmed` war; `unsubscribed` schreibt der Sync nie zurück); (b) in einzelnen Listen `unsubscribed`: die Kategorie fällt aus `profile.categories`; (c) Bounces (`blocklisted` mit Bounce-Grund oder Listmonk-Bounce-API, **Annahme** Doku `extern.md` nennt nur den eingehenden Webhook): `bounced`.
3. **Fremdadressen:** Eine Adresse auf einer `events-*`-Liste, die bei uns nicht `confirmed` mit `confirmed_at` ist (Admin-Import, Fremdanmeldung), wird aus den Listen ausgetragen (`remove`, nicht gelöscht, Listmonk ist geteilt) und als Zähler `foreignOnLists` in I25 gezeigt (PLAN A09).
4. **Fehlende:** Ein bei uns `confirmed` mit `mail_enabled` fehlt in Listmonk oder auf einer Soll-Liste: `upsert`-Auftrag einreihen.
5. Kampagnen mit `digest_run.status = 'draft'`: Status abfragen (4.4).
6. Ergebnis als Zähler im Log (nie Adressen) und im Status.

### 4.6 Pfade und Module

```
backend/app/modules/subscriptions/
  __init__.py
  models.py              SQLAlchemy-Modelle der Abschnitte 2.1 (subs)
  schemas.py             CamelModel-Ein- und Ausgaben (subs)
  db.py                  Subs-Engine und -Session (subs)
  consent.py             versionierte Einwilligungstexte (subs)
  interests.py           resolve_categories (rein), Seed-Lader (subs)
  tokens.py              Erzeugung, SHA-256-Hash, Magic-Link-Token (subs)
  emailkey.py            Kanonisieren, HMAC, pgcrypto-SQL (subs)
  doi.py                 Anmelden, Bestätigen, Mails (subs)
  manage.py              me-Routen, Rotation, Löschen (subs)
  router.py              /api/public/getstarted, /api/public/subscriptions/* (subs)
  altcha_router.py       /api/public/altcha/challenge (subs)
  ics_profile_router.py  /ics/p/{token}.ics (subs)
  ics_merge.py           ICS-Zusammenführung (subs, rein)
  enqueue.py             enqueue_outbox(session, op, subscriber_id) (subs; ruft nur INSERT ... ON CONFLICT)
  limits.py              IP- und Adress-Limit, Mindestdauer (subs)
  admin_router.py        lookup, erase, Digest-Freigabe, Statuszähler (subs)
  listmonk_port.py       Protocol und Wertklassen (listmonk)
  listmonk_client.py     httpx-Client (listmonk)
  listmonk_sync.py       Sollzustand, Listen-Auflösung (listmonk)
  outbox.py              Claim, Retry, Backoff, Breaker (listmonk)
  digest.py, digest_template.py   (listmonk)
  privacy.py             Aufruf der privacy_*-Funktionen, Audit (listmonk)
backend/worker/{outbox,reconcile,digest,privacy}.py
```

Registrierung: `app/api_routers.py` (subs) und `worker/main.py` (`functions` und `cron_jobs`, listmonk): `outbox_run` jede Minute, `reconcile_listmonk` 03:10, `build_digest_drafts` montags 05:00, `purge_expired` 03:20 (ruft die vier `privacy_*`-Funktionen), alle `unique=True`. Die Datei `app/modules/__init__.py`-Liste und `shared/permissions.py` (L9) ändert der subs-Builder.

## 5. Abuse und Datenschutz

### 5.1 ALTCHA

Kopie von `upstream/STUPA-Workflow/backend/app/shared/altcha.py` (HMAC-Challenge, `ReplayGuard`, `AltchaVerifier`) und der Abhängigkeiten `get_altcha_verifier`/`require_altcha` aus `shared/antiabuse.py` nach `backend/app/shared/` mit `PROVENANCE.json`-Einträgen; Settings `altcha_hmac_secret` (Min. 16 Zeichen; ohne Secret ist die Prüfung aus, **nur in `environment=development` erlaubt**, sonst Startfehler wegen `strict_security`), `altcha_max_number`, `altcha_challenge_ttl_seconds`. Route `GET /api/public/altcha/challenge` (404, wenn aus). Die Prüfung läuft lokal in der API (HMAC, Hash, Ablauf, Einmaligkeit in Redis); der Container `altcha` (Sentinel, Upstream `docker-compose.yml:263-293`) teilt nur das Secret und ist **nicht** im Prüfpfad. Frontend: Kopie von `altcha.service.ts` (Web Crypto, kein Fremdskript; CSP-konform), `solve()` je Anfrage neu. ALTCHA verlangen: `POST /subscriptions`, `POST /subscriptions/manage-link`. Nicht: `confirm` und `confirm/preview` (Token-Beweis), `GET`-Routen und die `me`-Routen (Token-Beweis).

### 5.2 Limits

- **Je IP:** 10 POSTs je Stunde auf `subscriptions` und `manage-link` zusammen (`RedisRateLimiter`, fail-open, Schlüssel `subs:ip:{ip}`), 429 mit `Retry-After`; `confirm`/`confirm/preview` 30 je Stunde; `me`-Routen 60 je Stunde je IP. nginx: `limit_req` 5 r/s für `/api/public/subscriptions` (7.4).
- **Je kanonischer Ziel-Adresse:** höchstens 3 Abo-Mails je Tag, **hart in der Datenbank** (`mails_count`/`mails_day`, ein bedingtes `UPDATE ... SET mails_count = CASE WHEN mails_day = current_date THEN mails_count + 1 ELSE 1 END ... WHERE NOT (mails_day = current_date AND mails_count >= 3) RETURNING`), weil der Redis-Limiter bei Ausfall alles durchlässt. Bei Überschreitung **kein 429**, sondern stilles Auslassen der Mail bei sonst gleicher Antwort (ein 429 je Adresse wäre ein Orakel und eine Waffe gegen Dritte). Für unbekannte Adressen wird zuerst die Zeile angelegt, damit der Zähler existiert; `pending`-Zeilen sind nach 48 h weg.
- Der Schlüssel des Adress-Limits ist die **kanonische** Adresse: Kleinschreibung, Unicode-NFKC, `+tag` im Lokalteil entfernt (`a+1@x`, `a+2@x` zählen als `a@x`), nur für den Zähler-Schlüssel `email_limit_hmac`; die Identität (`email_hmac`) behält das `+tag`, weil es ein anderes Postfach sein kann. Der DB-Zähler (`mails_count`) zählt je Identität; zusätzlich rechnet der Limiter pro Anfrage die Limit-HMAC (gleicher Schlüssel `EMAIL_HASH_KEY`, andere Eingabe) und zählt in Redis (`subs:addr:{limit_hmac}`, 3 je 24 h), damit auch `+tag`-Varianten gedeckelt sind.

### 5.3 Gleiche Antwort, gleiche Zeit (PLAN §18 Minor 2)

Ein Codepfad für bekannt und unbekannt: ALTCHA, Limits, Auflösung, HMAC, `SELECT ... FOR UPDATE`, INSERT oder UPDATE, Mail einreihen (Queue-Aufruf ist immer ein Redis-Zugriff, auch wenn `confirmed` nur den Hinweis-Text wechselt), Antwort. Die Antwort besteht aus Profil und `mail.requested`, enthält keine Aussage über den Adresszustand. **Feste Mindestdauer:** `limits.constant_time(started, minimum=0.6 s)` wartet mit `asyncio.sleep` bis `started + 0.6 s` (monotone Uhr) und liegt in `finally`, also auch bei Fehlern (429 ausgenommen: ein Limit-Treffer ist nicht adressabhängig). Gilt für `POST /subscriptions`, `POST /manage-link`, `POST /confirm`, `POST /confirm/preview` (404 und 200 gleich lang). Der Test misst nicht Wanduhrzeit gegen Schwellen allein, sondern vergleicht in einer Schleife (50 Läufe je Zustand) den Median bekannter, unbekannter und `unsubscribed`-Adressen: Differenz höchstens 40 ms; Dev-Vorgabe `MIN_RESPONSE_SECONDS` in Settings, der Test setzt sie auf 0,2 s.

Kanonisierung (`emailkey.py`): `strip`, NFKC, Domain in IDNA/Kleinschreibung, Lokalteil in Kleinschreibung; Validierung mit `email-validator` (Builder prüft, ob die Abhängigkeit schon in `pyproject.toml` steht, sonst ergänzen), Länge höchstens 254, kein `'`-freier Zwang: Apostroph ist erlaubt und wird beim Listmonk-Query verdoppelt; Steuerzeichen und Backslash werden abgewiesen. `email_hmac = HMAC-SHA-256(EMAIL_HASH_KEY, canonical)` Hex.

### 5.4 Tokens

DOI-, Verwaltungs- und ICS-Token: `secrets.token_urlsafe(32)` (256 Bit). In der Datenbank nur `sha256(token).hexdigest()`; Vergleich über die Datenbank (Gleichheitssuche auf dem Hash, kein Vergleich im Prozess). Token erscheinen nie in Logs, Audit, Fehlertexten, Metriken, Redis-Schlüsseln (Rate-Limit-Schlüssel enthalten IP oder HMAC, nie Tokens). **Pfadregeln:** nginx loggt `/ics/p/`, `/abo/` und `/bestaetigen/` redigiert (`log_format ev_token_redacted '$remote_addr [$time_local] "$request_method /$ev_token_prefix/..." $status $body_bytes_sent'`, Builder erweitert `ev_ics_redacted`), `Referrer-Policy: no-referrer` für alle drei, kein `proxy_cache`. Die SPA liest den Token aus der Route, hält ihn nur im Speicher und ersetzt die URL mit `history.replaceState` durch `/abo` (Verlauf und Screenshot-Werkzeuge sehen den Token danach nicht mehr; ein Reload verliert ihn bewusst und führt zu "Neuen Link anfordern").

### 5.5 Einwilligung

`consent_text_version` und `consent_categories` stehen mit `consent_at` im Datensatz (Nachweis, E16); bestätigt wird der Satz, den der Mensch gesehen hat (der Client sendet die `version`, der Server prüft sie gegen den aktuellen Stand). Checkbox-Text mit Link auf `/datenschutz` (Platzhalterseite aus B1, Inhalt B5). Die Versionen sind im Code für immer vorhanden (Golden-Test `tests/golden/consent.json`).

### 5.6 Admin-Auskunft und -Löschung

`POST /api/admin/subscribers/lookup` Body `{email}` (der Auftrag nennt GET; eine Adresse in der Query gehört in keinen Log, Abweichung 9.12) mit Recht `privacy.erase`: Antwort `SubscriberExportOut {found, status, createdAt, consentTextVersion, consentCategories, consentAt, confirmedAt, unsubscribedAt, profile: {interests, categories, mailEnabled, createdAt, lastFetchedOn}|null, outbox: [{op, state, createdAt}], listmonk: {present: bool, lists: [key]}|null}` als JSON (Auskunft nach DSGVO); nie die Adresse im Klartext zurück (die Person kennt sie, der Export bestätigt den Treffer nur), nie Token-Hashes. `POST /api/admin/subscribers/erase` Body `{email}`: `privacy_erase_subscriber`, Antwort 204 oder 404. Audit-Eintrag nur `{action: "subscriber.erase"|"subscriber.lookup", found: bool, by: sub}`.

### 5.7 Löschjobs (`worker/privacy.py`, täglich 03:20 UTC)

`privacy_purge_pending(now - 48 h)`, `privacy_anonymize_unsubscribed(now - 30 d)`, `privacy_purge_profiles(today - 12 months)`, `privacy_purge_outbox(now - 30 d)`; je Aufruf ein Audit-Eintrag mit Zähler (nur wenn > 0). Fehlgeschlagene `delete`-Aufträge (Listmonk down) bleiben mit Chiffrat liegen; ein `dead` `delete` ist ein Alarm in I25 mit Frist 24 h.

### 5.8 Logs

Kein Logger der Module `subscriptions`, `worker/{outbox,reconcile,digest,privacy}` schreibt Adressen, Tokens, Hashes, Listmonk-Antworttexte oder Interessen. Erlaubt: Status, Zähler, Fehlerklassen, Domains (wie `mail.py`). Test 8.2.

### 5.9 Gate B3 (nur dokumentieren, nicht blockieren)

Der Builder `backend-listmonk` schreibt `docs/B3-DATENSCHUTZ.md` (Vorlage für die Datenschutzbeauftragte: Löschkonzept aus 2.4/5.7, die Einwilligungstexte der Version 1, der DOI-Ablauf 3.2/3.3, die Daten, die an Listmonk gehen (Adresse, Listen, Attribute aus 4.1), Aufbewahrungsfristen 48 h/30 Tage/12 Monate, Fragen zum Listmonk-Betrieb und zur Absenderdomain (W3)). B3 wird **nicht** auf die Rückmeldung gewartet; ohne schriftliche Rückmeldung gilt B3 als "technisch fertig, Gate offen", und Go-live (B5) bleibt gesperrt (`docs/B3-ABNAHME.md` führt es als offen).

## 6. Frontend

Dateien unter `frontend/src/app/features/public/` (Muster der B1-Seiten: `pages/<name>/<name>.component.{ts,html,scss}`, Spec daneben). Alle Texte in `i18n/de` (neue Schlüsselgruppe `public.start.*`, `public.confirm.*`, `public.manage.*`, `public.subscribe.mail.*`), gegendert. Alle Seiten: ohne Cookie (kein `withCredentials` auf diesen Routen; der Interceptor liest das XSRF-Cookie nur für Schreibzugriffe mit Session), Handy zuerst (390×844), Tastaturbedienung, Fokus-Reihenfolge, `aria-live` für Fehler und Fortschritt, Touch-Ziele mindestens 44 px, axe ohne `critical`/`serious` (hell und dunkel).

Routen in `public.routes.ts` (alle `PUBLIC_DATA`): `start` → `StartPageComponent`; `bestaetigen/:token` mit `frame: 'bare'` → `ConfirmPageComponent`; `abo/:token` → `ManagePageComponent`; `abos` bleibt. Der Shell-Server (`publicapi/shell`) liefert für `/start`, `/abos` die Hülle mit festen Titeln; `/bestaetigen/*` und `/abo/*` liefern **nur** das nackte `index.html` mit `noindex` und ohne Tokens im `<head>` (Builder ergänzt `shell/router.py`; das Modul `publicapi` gehört seit B1 niemandem mehr exklusiv, die kleine Änderung steht in Abschnitt 11).

### 6.1 P06 Get started (`/start`)

`app-stepper` (vertikal auf dem Handy), Schritte:

1. **Interessen** (Chips aus der API, Mehrfachwahl, nichts vorausgewählt, `Weiter` deaktiviert mit "Wähl mindestens ein Interesse.") samt Frage 2 "Sitzungen und Gremien?" (`app-segmented` ja/nein).
2. **Fachschaft** (optional, Chips oder "Keine").
3. **Kanal** (`app-segmented`: "Nur Kalender" / "Kalender und Mail", Standard "Nur Kalender").
4. **Mail** (nur bei Mail): `app-input` Adresse, Einwilligungs-`app-checkbox` mit dem Satz aus `consent.template` (Kategorien eingesetzt) und Link "Datenschutz", ALTCHA unsichtbar (Lösung beim Absenden), Hinweistext "Wir schicken dir eine Bestätigung. Ohne Bestätigung speichern wir nichts."; bei Kalender-Kanal entfällt der Schritt.
5. **Ergebnis:** Zusammenfassung, ICS: Knopf "In Kalender-App öffnen" (`webcal://`), sichtbare `https://`-URL in einem schreibgeschützten Feld mit Knopf "Kopieren" (`navigator.clipboard`, Fehlertext "Link konnte nicht kopiert werden. Markier ihn bitte von Hand."), Hinweis Google ("Am Computer unter Weitere Kalender, Per URL hinzufügen") und "Änderungen kommen mit Verzögerung an." Bei Mail: `app-note` "Wir haben dir eine Bestätigungsmail geschickt." (derselbe Text, ob die Adresse bekannt war oder nicht, 5.3), Link "Abo verwalten" (erklärt, dass der Link per Mail kommt). **Kein QR-Code** (Auftrag; im ui-kit gibt es ihn ohnehin nicht).

Zustand: Antworten in `sessionStorage` (try/catch, Seite rendert ohne), Zurück behält Eingaben; der Token der Antwort (`icsUrl`) wird **nie** gespeichert, ein Reload der Ergebnisseite führt zurück zu Schritt 1. Fehlerzeilen (PLAN 15.2): "Das sieht nicht wie eine Mailadresse aus." · "Bitte bestätige die Einwilligung." · "Die Prüfung gegen Spam hat nicht geklappt. Bitte versuch es noch einmal." · "Zu viele Versuche. Bitte warte 15 Minuten." (aus `Retry-After`).

### 6.2 P07 Abos (`/abos`)

Der bestehende Abschnitt "Mail und Profil: kommt bald" (`subscribe.component.html`) wird durch einen Block "Persönlich: Interessen wählen" mit Knopf "Get started" (Link `/start`) und dem Satz "Mail-Abo gibt es nur mit Bestätigung." ersetzt; die Zeile "Verwaltungslink anfordern" öffnet einen `app-dialog` mit Adressfeld und ALTCHA (ruft `manage-link`, Antwort immer "Wenn die Adresse bei uns angemeldet ist, ist der Link unterwegs.").

### 6.3 P08 Bestätigen (`/bestaetigen/:token`, Rahmen `bare`)

Beim Laden `POST confirm/preview`; Treffer: `app-card` mit "Du willst Mails zu {Kategorien} bekommen." und Knopf "Abo bestätigen" (POST `confirm`), danach "Danke, dein Abo ist aktiv." und Link "Abo verwalten" (erklärt: kommt per Mail, kein Token auf der Seite). 404: `app-note` "Dieser Link ist abgelaufen oder wurde schon benutzt. [Neu anmelden]" (Link `/start`). Link-Scanner sehen nur das Shell-HTML (GET), nichts ändert sich. `history.replaceState` auf `/bestaetigen` nach dem Laden.

### 6.4 P09 Verwalten (`/abo/:token`)

Lädt `GET me` (Token im Header). Abschnitte: **Interessen** (Chips wie P06, speichern mit `PUT`), **Mail** (`app-switch` an/aus), **Kalender** (Erklärung: "Deinen Kalender-Link zeigen wir nur einmal beim Anlegen. Du kannst jederzeit einen neuen erzeugen." und Knopf "Neue URL erzeugen" mit Rückfrage "Der alte Link hört dann auf zu funktionieren."; Antwort zeigt `webcal`/`https` wie P06), **Löschen** (`app-button` danger "Alles abbestellen und Daten löschen", `app-dialog` mit Bestätigung; danach "Erledigt. Wir haben deine Adresse und dein Profil gelöscht."). Fehler: "Dieser Verwaltungslink ist ungültig." mit Feld "Neuen Link anfordern". Ein Nutzer ohne Profil sieht keine Kalender-Karte.

### 6.5 Zustand und API-Schicht

`api/subscriptions-api.service.ts` (HttpClient, `withCredentials: false`), `model/subscriptions.models.ts`, `model/questionnaire-state.ts` (reiner Zustand, signals), `ui/altcha.service.ts` (Kopie aus Upstream). Die Fehler werden wie in `public-error.ts` auf Problem+JSON-Codes gemappt (`altcha_invalid`, `rate_limited`, `consent_outdated`, `invalid_token`, `unknown_interest`, `no_interest`).

### 6.6 Keine externen Requests

Die Netzwerk-Allowlist-E2E aus B1 (nur eigene Origin, kein `Set-Cookie`, `context.cookies()` leer) läuft über alle neuen Seiten mit.

### 6.7 Playwright-Helfer

`frontend/e2e/support/mailpit.ts`: `waitForMail(to, subjectPart)` fragt die Mailpit-API (`http://127.0.0.1:8025/api/v1/messages`, `/message/{id}`) ab und liefert Text samt dem ersten Link `…/bestaetigen/<token>` bzw. `…/abo/<token>`; `deleteAll()` leert zwischen den Tests. Die Mails gehen über den Worker (`SMTP_HOST=localhost SMTP_PORT=1025 SMTP_STARTTLS=false`, 7.3).

## 7. Dev-Stack

### 7.1 `deploy/docker-compose.dev.yml` (erweitern)

Neue Dienste (alle Loopback, Wegwerf-Zugangsdaten, wie die vorhandenen):

| Dienst | Image (Builder pinnt und prüft das Tag) | Host-Port | Zweck |
|---|---|---|---|
| `listmonk-db` | `postgres:16-alpine`, eigene DB `listmonk` | keiner | Listmonk-Datenbank |
| `listmonk` | `listmonk/listmonk:v5.1.0` (**Annahme** Tag; Builder prüft gegen Docker Hub und die laufende Admin-API) | `127.0.0.1:9002:9000` | Listmonk, Befehl `sh -c "./listmonk --install --idempotent --yes --config '' && ./listmonk --config ''"`, Umgebung `LISTMONK_app__address=0.0.0.0:9000`, `LISTMONK_db__host=listmonk-db`, `LISTMONK_ADMIN_USER`/`LISTMONK_ADMIN_PASSWORD` |
| `mailpit` | `axllent/mailpit` (Tag pinnen) | `127.0.0.1:1025` (SMTP), `127.0.0.1:8025` (UI/API) | fängt alle Mails ab: Abo-Mails der API und Listmonk-Kampagnen |
| `altcha` | `ghcr.io/altcha-org/sentinel:1.31.1` (Tag aus Upstream `deploy/docker-compose.yml`) | keiner | nur Parität zum Produktions-Stack; die API prüft lokal (5.1); darf der Builder weglassen, wenn er im Dev-Stack keinen Nutzen belegt (Abweichung 9.13) |

Die API läuft auf dem Host (`dev-up.sh`), erreicht Listmonk also über `http://127.0.0.1:9002`, das `LISTMONK_ALLOWED_HOSTS` (`127.0.0.1`) erlaubt. `deploy/docker-compose.yml` (Produktionsform) bekommt `altcha` und die Umgebungsdurchreichung der neuen Secrets, **nicht** Listmonk und Mailpit (Listmonk ist extern, PLAN 2.1); `compose-lint.sh` bleibt grün (Mem-Limits für `altcha`).

### 7.2 Seed: `deploy/listmonk-seed.sh` (idempotent, von `dev-up.sh` aufgerufen)

Wartet auf `GET /api/health`; richtet den SMTP-Ausgang von Listmonk auf Mailpit (`PUT /api/settings`, **Annahme** Schema, Builder prüft); legt den API-Nutzer `events-api` an (Admin → Users, `POST /api/users` mit `type: api`, **Annahme**; Builder prüft Anlage und Token-Rückgabe gegen v5; die Token-Ausgabe schreibt das Skript in `backend/.env` nur, wenn die Schlüssel dort fehlen) und die Liste `events-alle` sowie je aktive Kategorie `events-<slug>` per API (`POST /api/lists`). Die Rechtebeschränkung des API-Nutzers auf `events-*` (Listen-Rolle) ist in Listmonk eine Rolle mit konkreten Listen-IDs, nicht mit Muster: das Skript legt sie für die vorhandenen Listen an; neue Listen hängt `ensure_list` an die Rolle an, **wenn** der Endpunkt es erlaubt (Builder prüft), sonst Warnung und Handarbeit in `docs/secrets.md` (Weiche B3-3).

### 7.3 Umgebung

`deploy/.env.host.example` und `deploy/.env.example` (Namen nach PLAN 11.3): `SUBS_DATABASE_URL=postgresql+asyncpg://events_subs:dev-subs@localhost:5434/events`, `EVENTS_SUBS_PASSWORD`, `ALTCHA_HMAC_SECRET`, `ALTCHA_ROOT_PASSWORD` (nur Compose), `PGCRYPTO_EMAIL_KEY`, `EMAIL_HASH_KEY` (je mindestens 32 Zeichen, frisch, nie gleich), `LISTMONK_URL=http://127.0.0.1:9002`, `LISTMONK_API_USER`, `LISTMONK_API_TOKEN`, `LISTMONK_ALLOWED_HOSTS=127.0.0.1`, `SMTP_HOST=localhost`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`, `MIN_RESPONSE_SECONDS=0.6`. `settings.py` ergänzt die Felder; `load_settings` verlangt im Produktionsmodus (`strict_security`) `altcha_hmac_secret`, `pgcrypto_email_key`, `email_hash_key`, `subs_database_url`, `listmonk_*` und prüft gegenseitige Verschiedenheit der Schlüssel. `docs/secrets.md` bekommt die Rotation: `PGCRYPTO_EMAIL_KEY` und `EMAIL_HASH_KEY` rotieren **nicht** ohne Migration (Neuverschlüsselung beziehungsweise Neuberechnung aller Hashes; steht als Verfahren in der Datei, Builder schreibt es). `gitleaks` bleibt in CI.

### 7.4 nginx (`deploy/web/nginx.conf`, `snippets`)

- Neue Locations `^~ /abo/` und `^~ /bestaetigen/`: `try_files` auf die SPA (`index.html`, wie die übrigen SPA-Pfade), `access_log … ev_ics_redacted`-artig redigiert (neues Format `ev_token_redacted`), `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, kein `proxy_cache`, mit den Sicherheits-Headern aus `snippets/security-headers.conf` (compose-lint verlangt den Include in jeder Location).
- `/ics/p/` bleibt wie in B1 (redigiert, kein Cache); `location ^~ /api/public/subscriptions` mit `limit_req zone=ev_public burst=10`, `proxy_cache` aus.
- `compose-lint.sh` (Builder erweitert): jede Location unter `/abo/`, `/bestaetigen/`, `/ics/p/` nutzt ein redigiertes Log-Format und kein `proxy_cache`.

### 7.5 `dev-up.sh`

Ergänzt die Wartezeit auf Listmonk (`curl -fs http://127.0.0.1:9002/api/health`), ruft `deploy/listmonk-seed.sh` auf, startet den Worker mit denselben Variablen (`-p EnvironmentFile`). Units unverändert: `stupa-api`, `stupa-worker`, `stupa-ng`.

## 8. Tests

### 8.1 Unit (`backend/tests/unit/subscriptions/`)

Interesse → Kategorien (`resolve_categories`: Einzelinteresse, Mehrfach, `fachschaft:<slug>`, Eltern- und Kind-Kategorien, "nur Partys, keine Sitzungen" ergibt kein `sitzung`, unbekannter Slug, leere Menge, Obergrenze 40); Kanonisierung der Adresse (Großschreibung, IDNA, NFKC, `+tag` nur im Limit-Schlüssel, Apostroph, Steuerzeichen); HMAC-Determinismus; Token-Erzeugung und `sha256`-Hash (43 Zeichen, nie gleich, Hash nicht rückrechenbar); **Timing-Konstanz** (`constant_time` mit gefälschter Uhr: sowohl Erfolg als auch Fehler warten bis zum Minimum); Einwilligungs-Golden (alle Versionen byte-gleich); ICS-Merge (Deduplizierung nach `UID`, ein `VTIMEZONE`, deterministische Reihenfolge, Faltung/CRLF bleiben); Digest-Template (Escapes: Titel `{{ .Subscriber.Email }}` bleibt Text, HTML in Titeln wird maskiert, kein `StrictUndefined`-Fehler); Backoff-Berechnung; Sollzustand `desired_lists` (Mail aus, Listmonk-`unsubscribed` gewinnt); Mindest-Port-Verträge am Fake.

### 8.2 Integration (`backend/tests/integration/subscriptions/`, echtes Postgres per Testcontainer mit `alembic upgrade head`, `roles.sql` beide Stufen)

- **DOI-Flow:** Anmeldung → `pending` + Mail-Job → `GET` auf die Seite und Preview ändern nichts → `POST confirm` setzt `confirmed`, Outbox-Eintrag, Token einmalig (zweiter Versuch 404), nach 24 h 404, Verwaltung-Token nach 2 h 404.
- **Gleiche Antwort für bekannte und unbekannte Adressen:** Körper und Status byte-gleich für unbekannt, `pending`, `confirmed`, `unsubscribed`, `bounced`, `erased`; Zeitvergleich 8.1.
- **Limits:** 11. Anfrage je IP und Stunde 429; vierte Mail je Adresse und Tag wird still ausgelassen (Zähler bleibt 3, Antwort gleich), auch mit ausgeschaltetem Redis (Fail-open-Pfad); ALTCHA: fehlend, kaputt, abgelaufen, wiederverwendet je 400.
- **Outbox mit Fake-Listmonk:** `upsert` legt Subscriber und Listen an; Fehler wiederholt mit Backoff; Listmonk down: `confirm` klappt, Outbox wächst, nichts geht verloren, Wiederherstellung arbeitet nach; Idempotenz (zweimal einreihen = ein Aufruf); Circuit-Breaker nach fünf Fehlern; `dead` nach zehn.
- **Abgleich:** Abmeldung in Listmonk wird übernommen; `unsubscribed` bleibt `unsubscribed` nach `upsert` und Abgleich ("Abmeldung bleibt nach Abgleich"); Fremdadresse auf `events-*` wird ausgetragen; fehlende Adresse wird nachgetragen; Einzelliste `unsubscribed` entfernt die Kategorie.
- **Löschen:** `DELETE me` entfernt Adresse, Profil, Token und (über den Fake) den Listmonk-Datensatz; danach 404 für den ICS-Token; Tombstone enthält keine PII (`SELECT` über alle Spalten). Löschjobs: `pending` älter 48 h weg, jünger bleibt; `unsubscribed` älter 30 Tage anonymisiert; Profile ohne Abruf 12 Monate weg; Profile mit Mail-Abo bleiben.
- **Digest:** Entwurf wird angelegt (Fake hält `draft`), zweiter Lauf legt nichts doppelt an, Freigabe-Knopf gesperrt bei Abweichung `subscriber_count`, Freigabe setzt `released`; Freigabe im Listmonk wird erkannt.
- **Profil-ICS:** gültiger Token liefert genau die Events des Profils (nur Partys, keine Sitzungen: kein Sitzungs-Event im Kalender); ETag/304; Rotation: alter Token 404, neuer 200; unbekannt, rotiert, widerrufen (Löschen) liefern **byte-gleiche** 404; Abruf aktualisiert `last_fetched_on` einmal je Tag; Token nie in `caplog` und nie im Uvicorn-Access-Log (App-Start mit Standard-Logger, Zugriff mit Token, `caplog` und `capfd` durchsucht).
- **`events_subs`-Grants** (`test_db_grants_roles_sql.py` erweitert): Rolle kann `subscriber`, `subscription_profile`, `outbox`, `listmonk_list`, `digest_run` lesen, einfügen, ändern; **kann nicht** löschen (`DELETE` und `TRUNCATE` scheitern); kann `event`, `audit_entry` und andere Tabellen nicht lesen; kann `public_event_v` lesen; darf `privacy_*` ausführen; `events_public` und `events_app` sehen die Subs-Tabellen nicht; `log_parameter_max_length` der Rolle ist 0.
- **Kanarienvogel** (`tests/integration/publicapi/test_canary.py` erweitert): eine E-Mail-Adresse und ein Token-Marker, die über Get started angelegt wurden, tauchen weder im Feed, in keinem ICS (Kategorie, `all`, Einzel, Profil), im Sitemap-Snapshot, im `caplog`, im Audit noch im Redis auf (Schlüssel und Werte durchsucht), außer im Mail-Job-Körper und in der Chiffre-Spalte.
- **Postgres-Parameter-Log:** ein absichtlicher Fehler in `emailkey`-SQL unter Rolle `events_subs`, Log des Containers enthält den Schlüssel nicht (Builder belegt die Aussage aus 2.3).
- **SSRF/Client:** Allowlist (fremder Host, `https` erzwungen, Redirect nicht gefolgt), Timeouts, Apostroph in der Adresse (`o'brien@…`) im Query, Fehlertexte ohne Antwortkörper.

Gegen den **echten lokalen Listmonk** (Marker `listmonk`, nicht im Standardlauf; `deploy/dev-up.sh` genügt): Port-Verträge (`ensure_list`, `upsert`, Differenz hinzufügen und entfernen ohne `PUT` auf den Subscriber, `blocklist`, `delete`), Kampagne als `draft`, Freigabe, `subscriber_count`; Abgleich-Lauf nach einer Abmeldung über den Listmonk-Link; Mehrfach-Listen-Anmeldung erzeugt **keine** Listmonk-Opt-in-Mail (E16: nur `preconfirm_subscriptions`, Mailpit-Zähler 0).

### 8.3 Frontend

Jest: `StartPageComponent` (Schrittfolge, Weiter-Sperre ohne Interesse, Kanalwahl blendet Mail-Schritt, Zustand überlebt Zurück, Zustand nicht im Speicher nach Reload der Ergebnisseite, kein Token in `sessionStorage`), `questionnaire-state`, `ConfirmPageComponent` (Preview, POST-Knopf, 404-Text), `ManagePageComponent` (Laden, Speichern, Rotation mit Rückfrage, Löschen mit Dialog, Token nach `replaceState` weg), `SubscribePageComponent` (Mail-Block), API-Dienst (Header statt Query, `withCredentials: false`), `altcha.service` (Lösung, Wiederholung).

Playwright `frontend/e2e/getstarted.spec.ts` (gegen `ng serve` :4200 und Dev-Backend, Mailpit :8025):
1. **Fragebogen → ICS:** nur "Partys", Sitzungen "nein", Kanal "Kalender" → Ergebnisseite mit `webcal://` und `https://…/ics/p/<token>.ics`; der Link liefert `text/calendar`, enthält nur Party-Events (Fixtures aus `dev_events.yaml`), kein Sitzungs-Event; kein `Set-Cookie`, `context.cookies()` leer.
2. **Mail → DOI → Verwalten → Löschen:** "Kalender und Mail" mit `e2e-<zufall>@example.test` → Mailpit-Mail lesen, `GET` auf den Bestätigungslink zeigt die Seite, **ohne** zu bestätigen (zweiter Aufruf von `confirm/preview` unverändert; Status per Admin-Auskunft `pending`), Knopf "Abo bestätigen" → "Danke"; Outbox → Listmonk (nach `run`-Hilfe oder Warten ≤ 70 s): Subscriber in Listmonk; Verwaltungslink anfordern → Mail → `/abo/<token>`: Interessen ändern und speichern, ICS-URL neu erzeugen (alter Link 404, neuer 200), "Alles abbestellen und Daten löschen" → "Erledigt…"; Listmonk-Subscriber weg; Verwaltungslink danach "ungültig".
3. **Gleiche Antwort:** zweimal dieselbe Adresse anmelden (bekannt und unbekannt) liefert dieselbe Ergebnisseite.
4. **Netzwerk-Allowlist und axe** (hell/dunkel, 390×844 und 1280) über `/start`, `/abos`, `/bestaetigen/x`, `/abo/x`.

### 8.4 Contract und Lint

`test_public_module_builds_responses_field_by_field` und der Allowlist-Test gelten für neue Modelle nur dort, wo sie die View lesen; die Subs-Modelle sind kein Teil der Feed-Allowlist (`allowlist.py`, CODEOWNERS). Schemathesis (Standardlauf der Public-Routen) bekommt die neuen Pfade; ALTCHA und Limits sind im Test ausgeschaltet beziehungsweise überschrieben (`dependency_overrides`). `basedpyright`, `ruff`, `eslint`, `tsc`, `jest`, `npm run build` grün.

## 9. Abweichungen

1. **P08-Pfad:** `/bestaetigen/<token>` statt `/abo/bestaetigen/{token}` (PLAN 15.2 gewinnt, sonst kollidiert er mit `/abo/<manage-token>`). Gleicher Kontext: die GET-Seite ruft nur `confirm/preview` (POST) auf.
2. **Namen:** `subscriber.email_hmac` (PLAN/E18 `email_hash`), Tabelle `outbox` (PLAN `listmonk_outbox`), `subscription_profile` (PLAN `interest_profile`), Status `confirmed` (PLAN `active`), zusätzlich `bounced` und `erased` (PLAN `purged`); `subscriber_category` aus PLAN 3.3 entfällt, die Kategorien liegen als `text[]` im Profil.
3. **`consent_ip_hash` entfällt** (PLAN 3.3: keine IP im Datensatz).
4. **`digest_weekday` entfällt** (Digest je Liste, nicht je Person).
5. **`listmonk_list`-Tabelle** statt `category.listmonk_list_id` (getrennte Schreibrechte).
6. **Fünf Fragen ohne Ausschlüsse** statt PLANs fünf Schritte mit Ausschlüssen.
7. **Kategorien-Zusatz:** PLAN 8.7.3 hält neue Kategorien einer aktiven Adresse bis zur Bestätigung `pending`. Hier ändert ein öffentlicher Aufruf für eine bekannte Adresse **nichts** (nur Hinweis-Mail mit Verwaltungslink), und eine Änderung über den Verwaltungslink gilt sofort, weil der Link den Besitz der Mailbox beweist; die Einwilligungsversion wird dabei neu geschrieben.
8. **Token im Header** statt `?token=` für die `me`-Routen.
9. **Listmonk-Attribute:** `source`, `profile_version`, `profil_id`, `kategorien` (PLAN: nur die ersten beiden).
10. **Secret-Namen** `LISTMONK_API_USER/TOKEN` (PLAN 11.3) statt `LISTMONK_USER/TOKEN`; `SUBS_DATABASE_URL` statt PLANs `DB_SUBS_URL` (Muster `PUBLIC_DATABASE_URL`).
11. **"Automatisch planen"** (E17) nicht gebaut; nur Entwurf mit Freigabeklick.
12. **Auskunft per POST** statt GET (keine Adresse in Query-Strings).
13. **Container `altcha` im Dev-Stack** nur zur Parität, nicht im Prüfpfad.
14. **`shared/ssrf.py`** bekommt `allow_private`; sonst ließe sich ein Listmonk im Docker-Netz oder auf Loopback nicht ansprechen.
15. **`email-validator`, `httpx`** nur, falls noch nicht Abhängigkeit (Builder prüft `pyproject.toml`).

Offene Weichen für Luis (blockieren den Bau nicht, Standard in Klammern): B3-1 Zuordnung Interessen → Kategorien (Tabelle 2.1); B3-2 Verwaltung reiner Kalender-Profile (keine, Neuanlage); B3-3 Listen-Rolle des Listmonk-API-Nutzers (Handarbeit in Produktion); W3 (Betrieb, Absenderdomain, Auftragsverarbeitung, Datenschutz-Ansprechperson) aus PLAN 17.

## 10. Abnahme B3 (Wortlaut aus PLAN §16.2, B2 und B3, Gate B3)

> **B2** ICS je Profil, Token-Verwaltung, Abos-Seite (P07). **Fertig wenn:** Token nur als Hash, nie im Log (Test), Rotation invalidiert, unbekannt und widerrufen geben dieselbe 404.
>
> **Gate B3** Datenschutzbeauftragte hat Löschkonzept, Einwilligungstext, DOI-Ablauf und Listmonk-Betrieb gesehen (W3). **Fertig wenn:** schriftliche Rückmeldung liegt vor. (Dokumentieren, nicht blockieren: `docs/B3-DATENSCHUTZ.md`, 5.9.)
>
> **B3** Get started (P06), `subscriber` mit eigener DOI (P08), ALTCHA, Limits, Outbox, `ListmonkPort`, Abgleich, Digest als Entwurf mit Freigabe, Abo verwalten und löschen (P09), Löschkonzept-Jobs. **Fertig wenn:** "nur Partys, keine Sitzungen" ergibt Profil, ICS und passende Listen; GET auf den Bestätigungslink bestätigt nicht; gleiche Antwort für bekannte und unbekannte Adressen; Listmonk-down verliert nichts; Abmeldung bleibt nach Abgleich; Digest liegt als Entwurf; Löschen entfernt Adresse, Profil, Token und Listmonk-Datensatz.

| Spalte | Punkt | Nachweis |
|---|---|---|
| a | Token nur als Hash in der DB, nie im Log | 8.2 Profil-ICS (`caplog`, `capfd`, Access-Log), Kanarienvogel, nginx-Format 7.4 |
| b | Rotation invalidiert; unbekannt und widerrufen: dieselbe 404 | 8.2 Profil-ICS (byte-gleich) |
| c | "nur Partys, keine Sitzungen" → Profil, ICS, passende Listen | 8.1 `resolve_categories`, 8.2 Profil-ICS, Fake-Listmonk-Upsert, E2E 1 |
| d | GET auf Bestätigungslink bestätigt nicht | 8.2 DOI-Flow, E2E 2 |
| e | gleiche Antwort für bekannte und unbekannte Adressen (Minor 2) | 8.2 (Körper), 8.1 (Timing) |
| f | Listmonk-down verliert nichts | 8.2 Outbox |
| g | Abmeldung bleibt nach Abgleich | 8.2 Abgleich |
| h | Digest liegt als Entwurf | 8.2 Digest, echter Listmonk |
| i | Löschen entfernt Adresse, Profil, Token, Listmonk-Datensatz | 8.2 Löschen, E2E 2 |
| j | Limits, ALTCHA, Löschjobs | 8.2 Limits, Löschjobs |
| k | `events_subs` hat nur die vorgesehenen Rechte | 8.2 Grants |
| l | Gate B3 dokumentiert | `docs/B3-DATENSCHUTZ.md`; Rückmeldung offen |
| m | Gates (ruff, basedpyright, pytest, eslint, tsc, jest, build, compose-lint, smoke) und `docs/B3-ABNAHME.md` | wie `docs/B1-ABNAHME.md` Abschnitt A |

## 11. Verzeichnisbesitz

Jeder Builder fasst nur seine Pfade an; Berührung fremder Pfade ist eine Absprache über den Integrator und steht im Commit.

**`backend-subs`** (Modelle, DOI, Profil, ICS-Profil, Manage, ALTCHA-Routen):
`backend/app/modules/subscriptions/**` mit Ausnahme der Dateien von `backend-listmonk` (`listmonk*`, `outbox*`, `digest*`, `privacy*`); `backend/migrations/versions/0009_subscriptions.py` (alle Tabellen und `privacy_*`-Funktionen, 2.1 bis 2.4, inklusive `outbox`, `digest_run`, `listmonk_list`, damit es genau eine Migration gibt); `deploy/db/roles.sql` und `deploy/db/init-roles.sh` (Rolle `events_subs`, 2.5); `backend/seeds/interests.yaml`; `backend/app/shared/{altcha.py,antiabuse.py,permissions.py,ssrf.py}` (ALTCHA-Kopie, Rechte, `allow_private`); `backend/app/settings.py`, `backend/app/api_routers.py`; `backend/app/modules/publicapi/shell/router.py` (Hüllen für `/start`, `/bestaetigen/*`, `/abo/*`, klein, mit Absprache); `PROVENANCE.json`; Tests `backend/tests/unit/subscriptions/{test_interests,test_emailkey,test_tokens,test_limits,test_consent,test_ics_merge}.py`, `backend/tests/integration/subscriptions/{test_doi,test_manage,test_profile_ics,test_limits_int}.py`, `test_db_grants_roles_sql.py`, Kanarienvogel-Erweiterung.

**`backend-listmonk`**:
`backend/app/modules/subscriptions/{listmonk_port,listmonk_client,listmonk_sync,outbox,digest,digest_template,privacy}.py`; `backend/worker/{outbox,reconcile,digest,privacy}.py` und deren Registrierung in `backend/worker/main.py`; `backend/tests/_support/fake_listmonk.py`, `backend/tests/unit/subscriptions/{test_listmonk_sync,test_backoff,test_digest_template}.py`, `backend/tests/integration/subscriptions/{test_outbox,test_reconcile,test_digest,test_privacy,test_listmonk_client}.py`, `backend/tests/contract/test_listmonk_port.py`; Deploy: `deploy/docker-compose.dev.yml`, `deploy/docker-compose.yml` (nur `altcha` und Umgebung), `deploy/listmonk-seed.sh`, `deploy/dev-up.sh`, `deploy/.env.host.example`, `deploy/.env.example`, `deploy/compose-lint.sh`, `deploy/web/nginx.conf` (`/abo/`, `/bestaetigen/`, `/ics/p/`, `limit_req`), `docs/secrets.md`, `docs/B3-DATENSCHUTZ.md`; die Statuszähler für I25 (`GET /api/admin/status`-Erweiterung) in Absprache mit dem Besitzer des Admin-Moduls.

**`frontend`**: `frontend/**` (Seiten, Modelle, API-Dienst, ALTCHA-Dienst, `public.routes.ts`, i18n, Jest-Specs, `e2e/getstarted.spec.ts`, `e2e/support/mailpit.ts`, `ngsw-config.json` nur wenn `/abo/**` und `/bestaetigen/**` ausgeschlossen werden müssen: Navigation darf den Token nicht in den Cache schreiben, Builder prüft die bestehende Liste in `core/pwa/ngsw-navigation.spec.ts`).

**Reihenfolge:** (1) `backend-subs` committet zuerst Migration und `roles.sql` (sie legen den Branch `feat/b3-abos` an), (2) `backend-listmonk` und `frontend` arbeiten dann parallel; `subscriptions/enqueue.py` (subs) ist die einzige Brücke zwischen den Besitzern: `enqueue_outbox(session, *, op, subscriber_id, payload=None) -> None` mit dem Idempotenzschlüssel aus 2.1. (3) Integration: Gates, `scripts/b3_acceptance.py` (Muster `scripts/m5b_acceptance.py`), Playwright gegen Dev-Stack, `docs/B3-ABNAHME.md`.
