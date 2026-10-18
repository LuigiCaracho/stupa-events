# M2-Abnahme: Protokoll vom 18.10.2026

Lauf auf dem Entwicklungsrechner (NixOS, Docker lokal), Branch `feat/m1-durchstich`, nicht committet. Kein
Live-System berührt: IdP ist der lokale Keycloak (`127.0.0.1:8090`), alle Daten liegen in lokalen Containern.
Kriterium wörtlich: `docs/M2-KONTRAKT.md` Abschnitt 6.1 (PLAN §16.1, Zeile M2). Die Abschnitte A bis C stammen aus dem
Backend-Lauf und wurden im Integrationslauf (Abschnitt I) erneut ausgeführt; D ist der Frontend-Teil.

## Ergebnis

| Teil des Kriteriums | Ergebnis | Beleg |
|---|---|---|
| Matrix Rolle × eigene/fremde/keine Org × Route grün | erfüllt, exakte Statuscodes | `test_rbac_matrix.py` (12 Nutzer × 9 Operationen), `test_rbac_matrix_admin.py` (jede Route der Inventur × 12 Nutzer, aus der Katalog-Tabelle berechnet) |
| Partner-Testkonto bekommt 404 auf fremde Dossiers | erfüllt | A, `test_the_partner_account_gets_404_on_foreign_dossiers_and_guards` |
| Entfernen einer Gruppe im Dev-IdP entzieht den Zugriff nach der nächsten Revalidierung | erfüllt, mit Einschränkung D2 (unten) | A, Schritte a bis f |
| neue Route ohne Rechte-Deklaration lässt CI scheitern | erfüllt | `test_route_authz_inventory.py` (`ROUTE_PERMS` beidseitig, `SESSION_ONLY_ALLOWLIST`, zwei Meta-Tests) |
| `membership_sync` bei Login, Revalidierung, Mapping, Vertrauen | erfüllt | `test_membership_sync.py`, `test_membership_hooks.py` |
| Sitzungen widerrufen (eigene, Admin) | erfüllt | A, `test_sessions_revoke.py` |
| M1-Rest: Sicherheits-Header auf `/api/*` genau einmal | erfüllt, im Voll-Stack per `curl` gezählt | C1, I5 |
| M1-Rest: 5 `tsc`-Fehler, `typecheck` prüft die Specs | erfüllt | D |
| Frontend: Jest, Lint, Typecheck, Build, Playwright `m1.spec.ts` + `m2.spec.ts` | erfüllt (9/9 Playwright) | D |
| Routen-Inventur scheitert real an einer ungesicherten Route | erfüllt | I3 |

## A: API-Abnahme (`backend/scripts/m2_acceptance.py`)

Echter OIDC-Flow gegen Keycloak. Das Skript gleicht zuerst den laufenden Keycloak mit der Realm-Datei ab
(`scripts/keycloak_admin.py`), weil der Realm-Import nur beim ersten Start läuft. Gekürzte Ausgabe:

```
$ uv run --env-file .env python -m scripts.m2_acceptance
[m2] ok   admin role comes from the group: ['admin', 'member']           # BOOTSTRAP_ADMIN_* leer
[m2] ok   a: /auth/me names fsi/organizer
[m2] ok   a: the dossier of fsi is listed
[m2] b: removed organizer-fsi from events-fsi-organizer in Keycloak
[m2] ok   c: access holds before the revalidation is due -> 200
[m2] d: aged 5 session(s) by 5 hours                                      # UPDATE auth_session SET revalidated_at = now() - 5 h
[m2] ok   e: /auth/me shows no fsi after the revalidation
[m2] ok   e: the dossier is a 404 -> 404
[m2] ok   f: new login, fsi/organizer is back
[m2] ok   f: the dossier is readable again -> 200
[m2] ok   partner: submitter-ekhg gets 404 on an fsi dossier -> 404
[m2] ok   partner: T01 / T02 on the fsi dossier -> 404
[m2] ok   partner: the fsi dossier is not in the list
[m2] claim: cached groups before ['events-ekhg-submitter', 'events-users'], after [...same...] -> claim OMITTED, cache kept
[m2] ok   revoke: 1 other session(s) ended / the running session stays / the other session is anonymous -> 401
[m2] ok   revoke: admin ended 1 session(s) / the next request of the person is 401
[m2] M2 acceptance: all checks passed
```

`m1_acceptance.py` läuft unverändert grün (Organisationen vergleicht es jetzt als `(slug, role)`).

### Befund D2: Keycloak lässt den `groups`-Claim bei Nutzern ohne Gruppe weg

Das ID-Token des Refresh-Grants von `organizer-fsi` ohne jede Gruppe enthält **keinen** `groups`-Claim (kein leeres
Array). `verify_refreshed_id_token` behält dann den Cache (Entscheidung D2, vorsichtig). Folge: Wer seine **einzige**
Gruppe verliert, behält den Zugriff bis zum Admin-Knopf. Zwei Maßnahmen im Lauf:

- Der Dev-Realm hat die Gruppe `events-users` (PLAN 5.6 "Policy-Binding auf `events-users`") und jeder Testnutzer
  gehört dazu. Verliert er eine Rollengruppe, bleibt der Claim nicht leer, der Cache wird ersetzt, der Zugriff endet.
- Der Zusatzlauf entzieht `submitter-ekhg` beide Gruppen: Claim weggelassen, Cache bleibt (Zeile `claim:` oben).

Offen für Luis: Ob der Hochschul-Authentik denselben Claim weglässt, zeigt erst der Selbsttest E38 (M8). Bis dahin gilt
"jede reale Person steckt in `events-users`" als Annahme, und der Admin-Knopf ist der Rückfall.

## B: Backend-Gates

```
B1 $ uv run alembic heads                      -> 0003_roles_taxonomy (head)
   frische DB und M1-Upgrade ergeben dieselben Referenzzeilen (test_migrations); downgrade auf 0002 stellt die Slugs her
B2 $ ruff check . && ruff format --check .     -> All checks passed! / 250 files already formatted
   $ basedpyright                              -> 0 errors, 0 warnings, 0 notes
B3 $ PROVENANCE_STRICT=1 uv run pytest -m 'not e2e and not live' --cov    (testcontainers, Postgres 16)
     2529 passed, 1 xfailed in 217 s; Coverage 97.80 % (Gate 90 %)
     davon ohne Docker 2311, Integration 218
   $ uv run python -m scripts.coverage_critical -> ok (0 file(s) below 100 %)   # auth, audit, pipeline, publicapi
```

Der eine `xfail` ist die Zeile `test_a_member_reads_their_own_proposal` (strict, Grund "M3 Vorschläge").

## C: Betrieb

```
C1 $ deploy/compose-lint.sh                    -> compose-lint ok
   nginx:1.27-alpine mit den echten Dateien nginx.conf, security-headers.conf, api-proxy.conf (Upstream = Host-API):
   $ deploy/smoke.sh http://127.0.0.1:18081    -> smoke ok (15 locations)    # je Pfad jeder der fünf Header genau einmal
   ohne die fünf proxy_hide_header: "content-security-policy appears 2 times on /api/health" (der Test erkennt den Fehler)
```

Im Backend-Lauf lief nginx einzeln; den Voll-Stack hat der Integrationslauf gebaut (I5). `GET /api/auth/me` durch nginx
liefert `Referrer-Policy: strict-origin-when-cross-origin` (API direkt: `no-referrer`).

## Referenzdaten und Datenbank

- Kategorien 27, Organisationen 13 (nur `stupa` vertraut), 44 Orte (9 mit Anschrift, `lat`/`lon` leer, `hidden`).
- `events_app` darf `DELETE` auf `group_mapping` und `membership`, nicht auf `venue`, `organization`, `category`;
  `events_public` liest keine der drei Tabellen (`test_db_grants_roles_sql`).
- Dev-Datenbank migriert (`0003`), `roles.sql` Stufe 2 erneut, `seed_dev` hat 44 Zuordnungen angelegt.

## D: Frontend

```
$ npm run lint                                  -> keine Meldung
$ npm run typecheck                             -> tsc app + tsc spec ohne Fehler   # Skript prüft jetzt auch die Specs (6.3)
$ npx tsc -p e2e/tsconfig.json --noEmit         -> ohne Fehler
$ npx jest                                      -> 77 suites, 576 passed, 4 skipped, 1 todo
$ npm run build                                 -> Application bundle generation complete
$ PLAYWRIGHT_BROWSERS_PATH=$(nix build --no-link --print-out-paths nixpkgs#playwright-driver.browsers) \
  PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true E2E_BASE_URL=http://localhost:4200 \
  npx playwright test e2e/m1.spec.ts e2e/m2.spec.ts
  [5/9] editor: Verwaltung shows the taxonomy tabs and creates a category
  [6/9] editor: the mapping tab is not reachable                       # /forbidden, API 403
  [7/9] admin: adds a group mapping and removes it again               # danach events-system:… -> 422 reserved_group_prefix
  [8/9] organizer-fsi: a dossier of another organization answers not found
  [9/9] Sitzungen widerrufen: the other session needs a new login, this one stays
  9 passed (23.3s)
```

Erster Lauf: `admin: adds a group mapping` scheiterte, weil die Spec mit `getByRole('option').first()` die
Leer-Zeile "Keine Organisation" des Selects wählte (gewolltes Verhalten von `app-select` bei nicht-Pflichtfeldern) und
die Validierung "Org-Rolle braucht eine Organisation." korrekt griff. Die Spec wählt jetzt "Fachschaft Informatik".
Ergänzt (Kontrakt 6.2 Punkt 9 (1)): Die Spec versucht danach `events-system:<stamp>` als Redaktion anzulegen; die API
antwortet 422 und die Zeile zeigt "Gruppe beginnt mit reserviertem Präfix events-system:.".
Zusätzlich per Wegwerf-Spec (nicht im Repo) gesehen: `/verwaltung/orte` listet die Orte; der Schalter "Vertraut" ist
für `editor` gesperrt, für `admin` frei; `organizer-fsi` sieht keinen Eintrag "Verwaltung" und landet auf
`/verwaltung/orte` bei "403 Kein Zugriff".

## I: Integrationslauf (18.10.2026)

Aufbau wie M1: Dev-Stack lief (`docker-compose.dev.yml`, alle fünf Dienste healthy); API (`uvicorn :8000`), Worker
(`arq`) und `ng serve :4200` auf dem Host mit `backend/.env`, `LD_LIBRARY_PATH` mit `libstdc++` und `libmagic`.

```
I1 $ uv run alembic heads                       -> 0003_roles_taxonomy (head)
   $ uv run alembic upgrade head                -> aktuell
   $ psql -f /db/roles.sql                      -> DO DO DO
   $ python -m scripts.seed_dev   (zweimal)     -> 0 new group mapping(s) / 0 new dossier(s)
   Dev-DB: 27 Kategorien (+3 e2e-*), 13 Organisationen (1 vertraut), 44 Orte, 44 Zuordnungen, 6 Kinder unter fachschaft
I2 ruff check / format --check / basedpyright   -> All checks passed! / 250 files already formatted / 0 errors
   PROVENANCE_STRICT=1 pytest -m 'not e2e and not live' --cov   -> 2529 passed, 1 xfailed in 220 s, Coverage 97.80 %
   coverage_critical                            -> ok (0 file(s) below 100 %)
   m1_acceptance                                -> M1 acceptance: all checks passed
   m2_acceptance                                -> M2 acceptance: all checks passed (Ausgabe wie A)
I3 Routen-Inventur: GET /api/admin/principals/debug-unguarded ohne Gate in principals_router.py eingefügt
   $ pytest tests/unit/test_route_authz_inventory.py
     FAILED test_every_route_is_gated_or_explicitly_public  ['GET /api/admin/principals/debug-unguarded: no gate']
     FAILED test_every_route_has_an_expected_permission_set  {'unlisted': [('GET', '/api/admin/principals/debug-unguarded')]}
     2 failed, 4 passed
   Route wieder entfernt (Datei aus Sicherung zurück) -> 6 passed
I4 Eigenes Skript neben m2_acceptance (Keycloak-Admin-API, SQL per docker exec psql):
   organizer-fsi legt ein FSI-Dossier an
   organizer-makers (orgs [('makers','organizer')]): GET 404, PATCH {rev,title} 404, T01 404, nicht in der Liste
   Keycloak: organizer-fsi aus events-fsi-organizer entfernt -> vor Revalidierung GET 200, /auth/me [fsi/organizer]
   UPDATE auth_session SET revalidated_at = now() - interval '5 hours' (13 Sitzungen)
   -> /auth/me [], GET 404, membership-Zeilen der Person 0
   Gruppe zurück, neue Anmeldung -> /auth/me [fsi/organizer], GET 200
I5 Voll-Stack: ENV_FILE=.env.dev docker compose -f deploy/docker-compose.yml --env-file deploy/.env.dev up -d --build web
   (web, api, migrate, postgres, redis, minio; ohne Keycloak-Overlay, weil der Dev-Keycloak 8090 belegt)
   curl -D - je Pfad, Anzahl je Header:
     /api/health 200, /api/auth/me 401, /api/categories 401, /api/public/feed/events 200,
     /api/admin/group-mappings 401, / 200  -> je 1x CSP, Permissions-Policy, Referrer-Policy, X-Content-Type-Options, X-Frame-Options
   /api/auth/me: Referrer-Policy: strict-origin-when-cross-origin
   $ deploy/smoke.sh http://127.0.0.1:8081      -> smoke ok (15 locations)
   danach docker compose ... down (Volumes bleiben)
I6 deploy/compose-lint.sh -> ok; gitleaks detect (Historie) und gitleaks dir (alle 158 geänderten/neuen Dateien) -> no leaks found
```

Nachgeführt im Integrationslauf: `PROVENANCE.backend-m2.json` in `PROVENANCE.json` gemischt (Eintrag
`membership_sync.py`, Modus `U`), `npm run typecheck` prüft die Specs, Skill `frontend` kennt `features/admin`,
`permissionGuard` und `translations.admin.de.ts`, `CLAUDE.md` nennt `M2-KONTRAKT.md`.

## Offen

- Zahlen: Der Auftragstext nannte 25 Kategorien und 12 Organisationen, Kontrakt und Daten haben 27 und 13 (Luis bestätigt).
- Abweichungen des Frontends vom Auftragstext, dem Kontrakt folgend: `editor` legt keine Zuordnungen an
  (`admin.mappings` nur `admin`); "Andere Sitzungen widerrufen" beendet nur die anderen Sitzungen; GPS-Felder gesperrt
  ("ab Stufe C"); fremdes Dossier zeigt die bestehende Meldung statt einer eigenen 404-Seite (Kontrakt 6.2 Punkt 9 (4)).
- Prettier wurde über die neuen Frontend-Dateien nicht ausgeführt (ESLint grün).
- Lokale Reste: Testdossiers, drei `e2e-*`-Kategorien und Sitzungen in der Dev-DB; die Realm-Synchronisierung hat
  Nutzer und Gruppen im laufenden Keycloak angelegt.
- Verhalten des `groups`-Claims im Hochschul-Authentik (E38, M8); D2 bleibt bis dahin auf "Cache behalten".
- MinIO-Service-Konto (Betrieb), unverändert aus M1.

## N: Nachbesserung nach dem Review (18.10.2026)

Behoben: Leerzeichen-Eingaben (`Text`/`oidcGroup` streifen vor der Längenprüfung); Zyklen in der Organisationen-Kette
(`organization_cycle`, Frontend-Meldung); inaktive Organisationen vergeben keine Rolle mehr (`effective_grants`, Sync
läuft beim Umschalten von `active`); Sync mit `ON CONFLICT DO NOTHING` und einmal geladenen Zuordnungen; Matrix prüft
bei durchgelassenem Gate zusätzlich `< 500`; Referenzdaten als Literal und Hash gepinnt, Migration `0003` nicht mehr
von den Referenzmodulen abhängig (nur `venue_reference`, per Hash festgelegt); Test für IdP-Ausfall ohne Rechteverlust;
Fehlertexte der Verwaltung immer deutsch; Herkunftsvermerke "Pattern from" für Mappings/Principals/Frontend-Seite.
Neu festgehalten: Kontrakt Abschnitt 10, Punkte 10 und 11 (Venue-Slugs, `0003` nicht rein additiv). Das Jest-Gate
(Branches 94 %) war ohne Coverage-Lauf übersehen worden und ist wieder erfüllt (94,05 %).

```
ruff / basedpyright / alembic heads            -> grün, 0 errors, 0003 (head)
pytest unit                                    -> 2313 passed
pytest -m integration                          -> 223 passed, 1 xfailed
PROVENANCE_STRICT=1 pytest --cov               -> 2536 passed, 1 xfailed, Coverage 97.83 %; coverage_critical ok
eslint / tsc / build                           -> grün
jest --coverage                                -> 592 passed, Gates erfüllt (94,05 % Branches)
playwright m1 + m2 (Dev-Stack)                 -> 9 passed
```
