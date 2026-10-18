# M1-Abnahme: Protokoll vom 18.10.2026

Lauf auf dem Entwicklungsrechner (NixOS, Docker lokal), Branch `feat/m1-durchstich`, nicht committet. Kein
Live-System berührt: IdP ist der lokale Keycloak (`127.0.0.1:8090`), alle Daten liegen in lokalen Containern.
Kriterium wörtlich: `docs/M1-KONTRAKT.md` Abschnitt 9 (PLAN §16.1), lokale Lesart dort.

## Ergebnis

| Teil des Kriteriums | Ergebnis | Beleg |
|---|---|---|
| Login über den IdP, `/auth/me` mit Rolle aus einer Gruppe | erfüllt (Keycloak statt Authentik) | A1, E2E 1 |
| `events-fsi-organizer` legt Dossier an, Poster mit Alt-Text und Credit, fragt Freigabe an | erfüllt | A2, E2E 1 |
| `events-editor` gibt frei (T04, T05) | erfüllt | A2, E2E 4 |
| Event erscheint im Feed, Derivat abrufbar | erfüllt | A2, E2E 4 |
| ohne Poster: Freigabe 422 `image_required` | erfüllt | A3, E2E 3 |
| direktes SQL scheitert am Trigger (UPDATE und INSERT) | erfüllt, SQLSTATE 23514 | A4, `test_db_nets` |
| `alembic upgrade head` auf frischer DB, genau ein Head | erfüllt | B1 |
| Audit-Kette verifiziert, Audit-Hash-Test grün | erfüllt | A5, B3 |
| `test_provenance` grün | erfüllt (`PROVENANCE_STRICT=1`, ganzes Repo) | B3 |
| `compose-smoke` findet CSP in jeder Location | erfüllt (15 Pfade + statische Prüfung aller `location`-Blöcke) | C1 |
| VM-RAM gemessen, ClamAV-Entscheidung (E23) | **lokal gemessen**, VM offen | C3 |
| `backup.sh` und ein Restore einmal gelaufen | erfüllt, lokal (Dev-Stack und Voll-Stack) | C2 |
| `CLAUDE.md` und Skills `auth`, `events`, `pipeline` | erfüllt (`.claude/skills/be-{auth,events,pipeline}`) | |

## Aufbau

```bash
docker compose -f deploy/docker-compose.dev.yml up -d          # postgres 5434, redis 6381, minio 9100, clamav 3311, keycloak 8090
cp deploy/.env.host.example backend/.env                        # Host-Lauf: Issuer und Callback auf localhost
cd backend && uv sync
uv run alembic heads && uv run alembic upgrade head
docker exec stupa-events-dev-postgres-1 psql -v ON_ERROR_STOP=1 -U postgres -d events -f /db/roles.sql   # Stufe 2
uv run python -m scripts.seed_dev                               # zweimal: 3 neu, dann 0 neu
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run --env-file .env arq worker.main.WorkerSettings
cd ../frontend && npm ci && npx ng serve --port 4200             # Proxy /api -> :8000
```

Keycloak-Realm-Import geprüft: `GET /realms/stupa-events/.well-known/openid-configuration` liefert
`issuer=http://localhost:8090/realms/stupa-events`, die vier Testnutzer loggen sich ein, der Claim `groups`
kommt an (`/auth/me` unten). Die `/etc/hosts`-Zeile für `host.docker.internal` fehlt auf diesem Rechner; der
Host-Lauf braucht sie nicht, weil Browser und API Keycloak beide über `localhost` erreichen.

## A: API-Abnahme (`backend/scripts/m1_acceptance.py`)

Echter OIDC-Flow (Login-Formular, Code, Callback mit PKCE), kein Password-Grant. Gekürzte Ausgabe:

```
$ uv run --env-file .env python -m scripts.m1_acceptance
[m1] ok   organizer-fsi: /api/auth/login redirects
[m1] ok   organizer-fsi: Keycloak returns a code
[m1] ok   organizer-fsi: callback opens the session
[m1] ok   editor: callback opens the session
A1
[m1] ok   orgs [{'slug': 'fsi', 'role': 'organizer'}]
[m1] ok   editor roles ['editor', 'member']
A2
[m1] ok   create 'M1 Movienight 1792323323' (T00) -> 201
[m1] ok   poster upload with alt text and credit -> 201
[m1] ok   poster starts pending
[m1]      derivatives ['card1200', 'og1200x630', 'thumb400']        # ClamAV clean, derive_poster
[m1] ok   T01 on d492fec8 -> 200
[m1] ok   T02 on d492fec8 -> 200
[m1] ok   T04 on d492fec8 -> 403                                    # organizer darf nicht freigeben
[m1] ok   T04 on d492fec8 -> 200                                    # editor
[m1] ok   T04 set slug 2026-11-01-m1-movienight-1792323323
[m1] ok   T05 on d492fec8 -> 200
[m1] ok   feed sets no cookie
[m1] ok   event appears in the feed
[m1] ok   feed image http://localhost:4200/api/public/media/b9f0edad4bed8e59-card_1200.webp
[m1] ok   derivative served as webp (4474 bytes)
A3
[m1] ok   T04 on 7b0c51cf -> 422
[m1] ok   T04 without poster: code image_required
[m1] ok   reasons[] ['image_required']
[m1] ok   guards: T04 not allowed
A4  (als events_app, DATABASE_URL)
[m1] ok   SQL UPDATE state=live fails with 23514 (event 7b0c51cf-... cannot be live without a valid poster or image ...)
[m1] ok   SQL UPDATE state=approved fails with 23514 (...)
[m1] ok   SQL INSERT state=live fails with 23514 (...)
A5
[m1] ok   audit chain valid (58 entries)
[m1] M1 acceptance: all checks passed
```

Worker-Log dazu: `scan_attachment ● 'clean'`, danach `derive_poster ● 'derived'`.

## E2E (Playwright, `frontend/e2e/m1.spec.ts`)

Browser aus nixpkgs, `@playwright/test` auf die Driver-Version 1.63.0 gepinnt.

```
$ export PLAYWRIGHT_BROWSERS_PATH=$(nix build --no-link --print-out-paths nixpkgs#playwright-driver.browsers)
$ PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true E2E_BASE_URL=http://localhost:4200 npx playwright test e2e/m1.spec.ts
  ✓  1 organizer-fsi: login shows the role from the group (14.0s)
  ✓  2 organizer-fsi cannot approve its own dossier (1.6s)
  ✓  3 editor: approval without poster is refused with image_required (1.8s)
  ✓  4 editor: approves and publishes, the event appears in the feed (2.2s)
  4 passed (20.5s)
```

Test 1 deckt Login, Anlegen über den Dialog, Poster-Upload mit Alt-Text, Credit und Rechtegrundlage, T01 und T02
ab; Test 3 prüft die Guard-Liste in der UI ("Poster fehlt oder ist nicht freigegeben.", Bestätigen gesperrt) und
den 422 mit `fixAction=upload_poster`.

## B: Backend-Gates

```
B1 $ uv run alembic heads                      -> 0002_events_core (head)
   $ uv run alembic upgrade head  (frische DB, als events_migrator)
     Running upgrade  -> 0001_baseline ...
     Running upgrade 0001_baseline -> 0002_events_core ...
B2 $ ruff check . && ruff format --check .     -> All checks passed! / 210 files already formatted
   $ basedpyright                              -> 0 errors, 0 warnings, 0 notes
B3 $ PROVENANCE_STRICT=1 uv run pytest -m 'not e2e and not live' --cov    (testcontainers, Postgres 16)
     2341 passed in 200 s; Coverage 96.35 % (Gate 90 %)
     davon Unit 2209, Integration 132
   gezielt: test_provenance + test_publish_property (hypothesis) + tests/unit/audit -> 282 passed
   gezielt: test_db_grants, test_db_grants_roles_sql, test_rbac_matrix (Vollmatrix), test_db_nets,
            test_audit_chain, test_migrations -> 52 passed
```

`test_db_grants_roles_sql.py` (neu) führt das echte `deploy/db/roles.sql` auf einer frischen DB `events` aus
(Stufe 1, Migration als `events_migrator`, Stufe 2) und prüft: `events_migrator` besitzt alle Tabellen und Views;
`events_public` liest `public_event_v`, `SELECT` auf `event`, `organization`, `category`, `attachment`,
`audit_entry` scheitert mit `InsufficientPrivilege`; `events_app` hat kein `DELETE` auf Fachtabellen, kein
`UPDATE/DELETE/TRUNCATE` auf `audit_entry`, `event_revision`, `event_status_event`, kein DDL.

## C: Betrieb

```
C1 $ deploy/compose-lint.sh                   -> compose-lint ok   (inkl. neuer Prüfung: jede location hat den CSP-Include)
   Voll-Stack: docker compose -f deploy/docker-compose.yml --env-file deploy/.env.dev up -d --build
               (Postgres-Hostport per lokalem Override auf 5435, weil der Dev-Stack 5434 belegt)
   $ deploy/smoke.sh                           -> smoke ok (15 locations)
C2 $ COMPOSE_FILE=docker-compose.dev.yml ENV_FILE=.env.dev BACKUP_DIR=/tmp/stupa-backups deploy/backup.sh
     backup /tmp/stupa-backups/20261018T112619Z   (db.dump.age 72 kB, 3 Poster-Originale, manifest.json)
   $ BACKUP_DIR=/tmp/stupa-backups AGE_IDENTITY=secrets/backup-age.key deploy/restore-smoke.sh
     restore smoke ok (/tmp/stupa-backups/20261018T112619Z)   # Scratch-Container, Revision + Zeilenzahlen gleich
   dasselbe gegen den Voll-Stack (Projekt stupa-events): backup ... 20261018T112647Z, restore smoke ok
```

### C3: RAM, lokal gemessen (E23)

`docker stats --no-stream`, Voll-Stack im Leerlauf nach einem Upload, ClamAV mit geladenen Signaturen:

| Dienst | RAM | Limit |
|---|---|---|
| clamav | 949 MiB | 3 GiB |
| worker | 89 MiB | 768 MiB |
| api | 85 MiB | 512 MiB |
| minio | 82 MiB | 384 MiB |
| postgres | 34 MiB | 768 MiB |
| web | 14 MiB | 64 MiB |
| redis | 9 MiB | 320 MiB |
| **Summe** | **ca. 1,26 GiB** | |

ClamAV macht etwa drei Viertel aus. `CLAMD_CONF_ConcurrentDatabaseReload=no` wirkt (steht im erzeugten
`clamd.conf`), damit verdoppelt das Signatur-Update den Speicher nicht. Lokal gemessen, nicht auf der VM: die
Messung neben dem Workflow-Stack und die Entscheidung E23 stehen weiter offen. Der Keycloak des Dev-Stacks
(ca. 850 MiB) gehört nicht zur Produktion.

## Offen

- MinIO-Service-Konto, beschränkt auf `events-attachments` und `events-public`, per Init-Schritt in `deploy.sh`; bis dahin läuft die App mit dem Root-Konto des Objektspeichers.

## Während der Abnahme behoben

- `CsrfMiddleware` setzte `XSRF-TOKEN` auch auf `/api/public/*`; jetzt übersprungen, der Test ist kein `xfail` mehr.
- Alembic `fileConfig` schaltete bestehende Logger ab (`disable_existing_loggers`), dadurch war
  `test_storage_without_clamav_warns` in Gesamtläufen rot.
- Die Testsuite liest kein `backend/.env` mehr (sonst greifen Entwickler-Werte in Unit-Tests).
- Coverage misst mit `concurrency = ["greenlet", "thread"]`.
- Frontend rief `GET /api/orgs`; das Backend liefert `GET /api/organizations?creatable=true`.
- E2E-Helfer: Rollen-Locator statt `getByLabel` (Pflicht-Sternchen im Label), echte Kategorie statt "Optional".
- `backup.sh` hängte `mc` fest an das Netz `stupa-events_internal`; jetzt im Netz des MinIO-Containers, so laufen
  Dev- und Voll-Stack.
- `smoke.sh` prüft auch `/api/events/<id>/attachments`; `compose-lint.sh` prüft jede `location` statisch.
- Spec-Typfehler aus entfernten Workflow-Teilen (`USE_MOCK_API`, `nav.budget` u. a.) bereinigt.
- `PROVENANCE.json` aus den drei Teil-Dateien zusammengeführt (252 Einträge).
